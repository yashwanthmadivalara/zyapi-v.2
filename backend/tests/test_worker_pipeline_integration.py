import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import row, rows
from app.worker import JobWorker


@pytest.mark.integration
def test_real_worker_pipeline_with_authorized_video(tmp_path):
    video_path = os.getenv("VIRALFLOW_TEST_VIDEO")
    if not video_path:
        pytest.skip("Set VIRALFLOW_TEST_VIDEO to an authorized local video")
    source = Path(video_path)
    if not source.is_file():
        pytest.fail(f"Authorized test video does not exist: {source}")

    original = (settings.database_path, settings.upload_dir, settings.clip_dir, settings.whisper_model)
    settings.database_path = str(tmp_path / "worker-real.db")
    settings.upload_dir = str(tmp_path / "uploads")
    settings.clip_dir = str(tmp_path / "clips")
    settings.whisper_model = "tiny"
    settings.ensure_dirs()
    try:
        from app.main import app

        with TestClient(app) as client:
            with source.open("rb") as stream:
                response = client.post("/api/videos/upload?authorized=true", files={"file": (source.name, stream, "video/mp4")})
            assert response.status_code == 201, response.text
            video_id = response.json()["id"]
            job_id = response.json()["job_id"]
            worker_job = row("SELECT * FROM jobs WHERE id=?", (job_id,))
            JobWorker()._execute(worker_job)
            status = client.get(f"/api/videos/{video_id}/status")
            assert status.status_code == 200
            payload = status.json()
            assert payload["video"]["status"] == "analyzed"
            assert payload["jobs"][0]["status"] == "completed"
            assert payload["jobs"][0]["progress"] == 100
            assert payload["moments"]
            assert payload["clips"]
            assert rows("SELECT * FROM transcripts WHERE video_id=?", (video_id,))
            assert rows("SELECT * FROM subtitles WHERE clip_id=?", (payload["clips"][0]["id"],))
            assert Path(payload["clips"][0]["storage_path"]).is_file()
    finally:
        settings.database_path, settings.upload_dir, settings.clip_dir, settings.whisper_model = original
