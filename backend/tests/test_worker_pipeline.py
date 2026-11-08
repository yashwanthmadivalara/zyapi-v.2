import asyncio
from pathlib import Path

from app.config import settings
from app.db import connection, init_db, row
from app.worker import JobWorker, enqueue_job


def test_pipeline_worker_runs_all_stages_and_reuses_outputs(tmp_path, monkeypatch):
    original_db = settings.database_path
    original_clip_dir = settings.clip_dir
    settings.database_path = str(tmp_path / "pipeline.db")
    settings.clip_dir = str(tmp_path / "clips")
    try:
        init_db()
        source = tmp_path / "source.mp4"
        source.write_bytes(b"source")
        with connection() as con:
            con.execute(
                "INSERT INTO videos(filename,storage_path,sha256,size_bytes,duration_seconds,authorized,created_at) VALUES (?,?,?,?,?,?,?)",
                ("source.mp4", str(source), "pipeline-hash", source.stat().st_size, 30, 1, "now"),
            )
        job = enqueue_job(1, "pipeline", {"target_duration": 30, "clip_duration": 30})
        calls = []

        def fake_transcribe(video_id, payload, _existing_job_id=None):
            calls.append("transcription")
            with connection() as con:
                con.execute("INSERT INTO transcripts(video_id,text,model,segments_json,created_at) VALUES (?,?,?,?,?)", (video_id, "A transcript", "fake", '[{"start":0,"end":20,"text":"A transcript"}]', "now"))
            return {"video_id": video_id}

        async def fake_analyze(video_id, payload, _existing_job_id=None):
            calls.append("analysis")
            with connection() as con:
                con.execute("INSERT INTO moments(video_id,start_seconds,end_seconds,title,rationale,hook,category,caption,score,status,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", (video_id, 0, 20, "Moment", "Reason", "Hook", "general", "Caption", 8, "candidate", "now"))
            return {"video_id": video_id}

        def fake_extract(moment_id, payload):
            calls.append("clip_extraction")
            clip_path = Path(settings.clip_dir) / "clip.mp4"
            clip_path.parent.mkdir(parents=True, exist_ok=True)
            clip_path.write_bytes(b"clip")
            with connection() as con:
                cur = con.execute("INSERT INTO clips(video_id,moment_id,storage_path,start_seconds,duration_seconds,width,height,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)", (1, moment_id, str(clip_path), 0, 20, 1080, 1920, "generated", "now", "now"))
                return dict(con.execute("SELECT * FROM clips WHERE id=?", (cur.lastrowid,)).fetchone())

        def fake_subtitles(clip_id, subtitle_format="srt", burn_in=False):
            calls.append("subtitle_burning")
            Path(settings.clip_dir).mkdir(parents=True, exist_ok=True)
            Path(settings.clip_dir, f"clip-{clip_id}.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nA transcript\n", encoding="utf-8")
            Path(settings.clip_dir, f"clip-{clip_id}-subtitled.mp4").write_bytes(b"subtitled")
            return {"id": clip_id}

        import app.main as main
        monkeypatch.setattr(main, "transcribe_uploaded_video", fake_transcribe)
        monkeypatch.setattr(main, "analyze_video", fake_analyze)
        monkeypatch.setattr(main, "extract_moment", fake_extract)
        monkeypatch.setattr(main, "generate_subtitles", fake_subtitles)

        worker = JobWorker()
        worker._execute(job)
        assert calls == ["transcription", "analysis", "clip_extraction", "subtitle_burning"]
        completed = row("SELECT * FROM jobs WHERE id=?", (job["id"],))
        assert completed["status"] == "completed"
        assert completed["progress"] == 100
        assert completed["stage"] == "completed"
        assert row("SELECT COUNT(*) AS count FROM clips WHERE video_id=1")["count"] == 1

        worker._execute(completed)
        assert calls == ["transcription", "analysis", "clip_extraction", "subtitle_burning"]
        assert row("SELECT COUNT(*) AS count FROM clips WHERE video_id=1")["count"] == 1
    finally:
        settings.database_path = original_db
        settings.clip_dir = original_clip_dir
