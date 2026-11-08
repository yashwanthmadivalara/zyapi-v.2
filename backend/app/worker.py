import asyncio
import json
import logging
import threading
import time
from pathlib import Path

from .config import settings
from .db import connection, row, rows
from .services import now

logger = logging.getLogger("viralflow.worker")


def recover_interrupted_jobs() -> int:
    with connection() as con:
        cur = con.execute("UPDATE jobs SET status='pending',message='Recovered after application restart',updated_at=?,error_details=NULL WHERE status='processing'", (now(),))
        return cur.rowcount


def enqueue_job(video_id: int, kind: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    dedupe_key = f"{video_id}:{kind}:{json.dumps(payload, sort_keys=True)}"
    existing = row("SELECT * FROM jobs WHERE dedupe_key=? AND status IN ('pending','processing') ORDER BY id DESC LIMIT 1", (dedupe_key,))
    if existing:
        return existing
    stamp = now()
    with connection() as con:
        cur = con.execute("INSERT INTO jobs(video_id,kind,status,progress,message,created_at,updated_at,payload_json,dedupe_key) VALUES (?,?,?,?,?,?,?,?,?)", (video_id, kind, "pending", 0, "Queued", stamp, stamp, json.dumps(payload), dedupe_key))
        return dict(con.execute("SELECT * FROM jobs WHERE id=?", (cur.lastrowid,)).fetchone())


class JobWorker:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        recover_interrupted_jobs()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="viralflow-worker", daemon=True)
        self._thread.start()
        logger.info("Background worker started with max_concurrent_jobs=%s", settings.max_concurrent_jobs)

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _claim(self):
        with connection() as con:
            job = con.execute("SELECT * FROM jobs WHERE status='pending' AND cancel_requested=0 ORDER BY id LIMIT 1").fetchone()
            if not job:
                return None
            stamp = now()
            updated = con.execute("UPDATE jobs SET status='processing',started_at=?,updated_at=?,attempts=attempts+1,message='Processing' WHERE id=? AND status='pending'", (stamp, stamp, job["id"]))
            if not updated.rowcount:
                return None
            return dict(con.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone())

    def _run(self):
        while not self._stop.is_set():
            job = self._claim()
            if not job:
                self._stop.wait(settings.worker_poll_seconds)
                continue
            try:
                self._execute(job)
            except JobCancelled:
                logger.info("Job cancelled at safe boundary job_id=%s", job["id"])
            except Exception as exc:
                logger.exception("Job failed job_id=%s video_id=%s", job["id"], job.get("video_id"))
                detail = getattr(exc, "detail", None) or str(exc)
                with connection() as con:
                    con.execute("UPDATE jobs SET status='failed',error_details=?,message=?,stage='failed',updated_at=?,completed_at=? WHERE id=?", (detail, "Failed", now(), now(), job["id"]))

    def _update_stage(self, job_id: int, progress: int, stage: str, message: str | None = None):
        with connection() as con:
            con.execute("UPDATE jobs SET status='processing',progress=?,stage=?,message=?,updated_at=? WHERE id=?", (progress, stage, message or stage, now(), job_id))

    def _check_cancelled(self, job_id: int):
        current = row("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,))
        if current and current["cancel_requested"]:
            with connection() as con:
                con.execute("UPDATE jobs SET status='cancelled',stage='cancelled',message='Cancelled at safe stage boundary',updated_at=?,completed_at=? WHERE id=?", (now(), now(), job_id))
            raise JobCancelled()

    def _execute(self, job: dict):
        from .main import AnalysisIn, TranscriptionIn, analyze_video, transcribe_uploaded_video

        if row("SELECT cancel_requested FROM jobs WHERE id=?", (job["id"],))["cancel_requested"]:
            with connection() as con:
                con.execute("UPDATE jobs SET status='cancelled',message='Cancelled before processing',updated_at=?,completed_at=? WHERE id=?", (now(), now(), job["id"]))
            return
        payload = json.loads(job.get("payload_json") or "{}")
        if job["kind"] == "transcription":
            transcribe_uploaded_video(job["video_id"], TranscriptionIn(**payload), _existing_job_id=job["id"])
        elif job["kind"] == "analysis":
            asyncio.run(analyze_video(job["video_id"], AnalysisIn(**payload), _existing_job_id=job["id"]))
        elif job["kind"] == "pipeline":
            self._execute_pipeline(job, payload)
        else:
            raise ValueError(f"Unsupported job kind: {job['kind']}")
        with connection() as con:
            con.execute("UPDATE jobs SET status='completed',progress=100,stage='completed',message='Pipeline completed; clips ready for approval',updated_at=?,completed_at=? WHERE id=? AND status='processing'", (now(), now(), job["id"]))

    def _execute_pipeline(self, job: dict, payload: dict):
        from .main import AnalysisIn, ClipExtractIn, TranscriptionIn, analyze_video, extract_moment, generate_subtitles, transcribe_uploaded_video

        job_id = job["id"]
        video_id = job["video_id"]
        self._update_stage(job_id, 5, "queued", "Pipeline started")
        self._check_cancelled(job_id)

        transcript = row("SELECT id FROM transcripts WHERE video_id=?", (video_id,))
        if not transcript:
            self._update_stage(job_id, 10, "transcription", "Transcribing with Faster-Whisper")
            transcribe_uploaded_video(video_id, TranscriptionIn(model=payload.get("model"), language=payload.get("language")), _existing_job_id=job_id)
        self._update_stage(job_id, 25, "transcription", "Transcription complete")
        self._check_cancelled(job_id)

        moments = row("SELECT id FROM moments WHERE video_id=? AND status='candidate' ORDER BY score DESC LIMIT 1", (video_id,))
        if not moments:
            self._update_stage(job_id, 30, "analysis", "Analyzing transcript with Qwen")
            asyncio.run(analyze_video(video_id, AnalysisIn(target_duration=payload.get("target_duration", 30)), _existing_job_id=job_id))
        moments_list = rows("SELECT * FROM moments WHERE video_id=? AND status='candidate' ORDER BY score DESC LIMIT 3", (video_id,))
        if not moments_list:
            raise ValueError("Analysis produced no candidate moments")
        self._update_stage(job_id, 45, "clip_extraction", f"Preparing {len(moments_list)} candidate clips")
        self._check_cancelled(job_id)

        clips = []
        for index, moment in enumerate(moments_list):
            existing = row("SELECT * FROM clips WHERE moment_id=? AND status != 'rejected' ORDER BY id DESC LIMIT 1", (moment["id"],))
            if existing and Path(existing["storage_path"]).is_file():
                clip = existing
            else:
                clip = extract_moment(moment["id"], ClipExtractIn(duration_seconds=float(payload.get("clip_duration", 30))))
            clips.append(clip)
            self._update_stage(job_id, 45 + int(((index + 1) / len(moments_list)) * 30), "clip_extraction", f"Clip {index + 1}/{len(moments_list)} ready")
            self._check_cancelled(job_id)

        for index, clip in enumerate(clips):
            subtitle_path = Path(settings.clip_dir) / f"clip-{clip['id']}.srt"
            burned_path = Path(settings.clip_dir) / f"clip-{clip['id']}-subtitled.mp4"
            if not subtitle_path.is_file() or not burned_path.is_file():
                generate_subtitles(clip["id"], subtitle_format="srt", burn_in=True)
            self._update_stage(job_id, 75 + int(((index + 1) / len(clips)) * 20), "subtitle_burning", f"Subtitles ready for clip {index + 1}/{len(clips)}")
            self._check_cancelled(job_id)


class JobCancelled(Exception):
    pass


worker = JobWorker()
