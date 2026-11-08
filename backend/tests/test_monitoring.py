from app import monitoring
from app.config import settings
from app.db import connection, init_db


def test_parse_channel_input_supports_documented_forms():
    assert monitoring.parse_channel_input("UCabcdefghijk") == ("UCabcdefghijk", None)
    assert monitoring.parse_channel_input("https://www.youtube.com/channel/UCabcdefghijk") == ("UCabcdefghijk", None)
    assert monitoring.parse_channel_input("https://youtube.com/@creator_name") == (None, "creator_name")
    assert monitoring.parse_channel_input("@Click_path") == (None, "Click_path")
    assert monitoring.parse_channel_input("https://www.youtube.com/c/CreatorName/") == (None, "CreatorName")
    assert monitoring.parse_channel_input("https://example.com/channel/UCabcdefghijk") == (None, None)


def test_monitor_enabled_channels_records_errors_and_continues(tmp_path, monkeypatch):
    original = settings.database_path
    settings.database_path = str(tmp_path / "monitoring.db")
    try:
        init_db()
        with connection() as con:
            con.execute(
                "INSERT INTO monitored_channels(youtube_channel_id,channel_name,channel_url,monitoring_enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                ("UCabcdefghijk", "Test", "https://www.youtube.com/channel/UCabcdefghijk", 1, "now", "now"),
            )
        monkeypatch.setattr(monitoring, "monitor_channel", lambda channel: 2)
        result = monitoring.monitor_enabled_channels()
        assert result == {"checked": 1, "detected": 2, "errors": []}
    finally:
        settings.database_path = original


def test_monitoring_deduplicates_video_ids(tmp_path, monkeypatch):
    original = settings.database_path
    settings.database_path = str(tmp_path / "monitoring.db")
    try:
        init_db()
        with connection() as con:
            con.execute(
                "INSERT INTO monitored_channels(youtube_channel_id,channel_name,channel_url,monitoring_enabled,created_at,updated_at) VALUES (?,?,?,?,?,?)",
                ("UCabcdefghijk", "Test", "https://www.youtube.com/channel/UCabcdefghijk", 1, "now", "now"),
            )
        class Request:
            def __init__(self, payload): self.payload = payload
            def list(self, **kwargs): return self
            def execute(self): return self.payload

        class FakeYouTube:
            def channels(self):
                return Request({"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "PL1"}}}]})
            def playlistItems(self):
                return Request({"items": [{"contentDetails": {"videoId": "vid1"}, "snippet": {"title": "Title", "publishedAt": "2026-01-01T00:00:00Z"}}]})

        monkeypatch.setattr(monitoring, "_youtube", lambda: FakeYouTube())
        with connection() as con:
            channel = dict(con.execute("SELECT * FROM monitored_channels").fetchone())
        first = monitoring.monitor_channel(channel)
        second = monitoring.monitor_channel(channel)
        assert first == 1
        assert second == 0
    finally:
        settings.database_path = original
