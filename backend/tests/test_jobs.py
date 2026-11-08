from app.config import settings
from app.db import connection, init_db
from app.worker import enqueue_job, recover_interrupted_jobs


def test_job_enqueue_deduplicates_and_recovers(tmp_path):
    original = settings.database_path
    settings.database_path = str(tmp_path / "jobs.db")
    try:
        init_db()
        with connection() as con:
            con.execute("INSERT INTO videos(filename,storage_path,sha256,size_bytes,authorized,created_at) VALUES (?,?,?,?,?,?)", ("v.mp4", "v.mp4", "hash", 1, 1, "now"))
        first = enqueue_job(1, "transcription", {"model": "tiny"})
        duplicate = enqueue_job(1, "transcription", {"model": "tiny"})
        assert first["id"] == duplicate["id"]
        with connection() as con:
            con.execute("UPDATE jobs SET status='processing' WHERE id=?", (first["id"],))
        assert recover_interrupted_jobs() == 1
        with connection() as con:
            assert con.execute("SELECT status FROM jobs WHERE id=?", (first["id"],)).fetchone()[0] == "pending"
    finally:
        settings.database_path = original
