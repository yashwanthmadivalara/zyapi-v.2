from pathlib import Path

import pytest
from fastapi import HTTPException

from app.config import settings
from app.db import connection, init_db, row


def test_publishing_requires_approval_and_saves_remote_result(tmp_path, monkeypatch):
    original = (settings.database_path, settings.clip_dir, settings.youtube_client_id, settings.youtube_client_secret)
    settings.database_path = str(tmp_path / "publish.db")
    settings.clip_dir = str(tmp_path / "clips")
    settings.youtube_client_id = "client"
    settings.youtube_client_secret = "secret"
    settings.ensure_dirs()
    try:
        init_db()
        source = tmp_path / "clip.mp4"
        source.write_bytes(b"clip")
        with connection() as con:
            con.execute("INSERT INTO videos(filename,storage_path,sha256,size_bytes,authorized,created_at) VALUES (?,?,?,?,?,?)", ("source.mp4", str(source), "publish-hash", 4, 1, "now"))
            con.execute("INSERT INTO moments(video_id,start_seconds,end_seconds,rationale,hook,score,created_at) VALUES (?,?,?,?,?,?,?)", (1, 0, 10, "reason", "hook", 8, "now"))
            con.execute("INSERT INTO clips(video_id,moment_id,storage_path,start_seconds,duration_seconds,width,height,title,description,hashtags,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (1, 1, str(source), 0, 10, 1080, 1920, "Title", "Description", '["shorts"]', "rejected", "now", "now"))

        class UploadRequest:
            def next_chunk(self):
                return None, {"id": "remote123"}

        class Videos:
            def insert(self, **kwargs):
                assert kwargs["body"]["status"]["privacyStatus"] == "private"
                assert kwargs["body"]["snippet"]["title"] == "Title"
                return UploadRequest()

        class YouTube:
            def videos(self):
                return Videos()

        import app.main as main
        monkeypatch.setattr(main, "youtube_credentials", lambda: object())
        monkeypatch.setattr("googleapiclient.discovery.build", lambda *args, **kwargs: YouTube())
        monkeypatch.setattr("googleapiclient.http.MediaFileUpload", lambda *args, **kwargs: object())

        with pytest.raises(HTTPException) as rejected:
            main.publish_clip(1, main.PublishIn(visibility="private"))
        assert rejected.value.status_code == 409
        with connection() as con:
            con.execute("UPDATE clips SET status='approved' WHERE id=1")
        result = main.publish_clip(1, main.PublishIn(visibility="private"))
        assert result["status"] == "published"
        assert result["published_video_id"] == "remote123"
        assert result["published_url"].endswith("remote123")
        assert row("SELECT status FROM publishing_events WHERE clip_id=1 ORDER BY id DESC LIMIT 1")["status"] == "published"
    finally:
        settings.database_path, settings.clip_dir, settings.youtube_client_id, settings.youtube_client_secret = original
