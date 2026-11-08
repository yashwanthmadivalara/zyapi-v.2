import logging
import re
import threading
from datetime import datetime, timezone

from .config import settings
from .db import connection, row, rows
from .services import now
from .youtube_auth import credentials as youtube_credentials

logger = logging.getLogger("viralflow.monitoring")
CHANNEL_ID_RE = re.compile(r"^UC[a-zA-Z0-9_-]{10,}$")


def parse_channel_input(value: str) -> tuple[str | None, str | None]:
    value = value.strip()
    if CHANNEL_ID_RE.fullmatch(value):
        return value, None
    match = re.fullmatch(r"https?://(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_-]+)/*", value)
    if match:
        return match.group(1), None
    handle = re.fullmatch(r"https?://(?:www\.)?youtube\.com/@([a-zA-Z0-9._-]+)/*", value)
    if handle:
        return None, handle.group(1)
    standalone_handle = re.fullmatch(r"@([a-zA-Z0-9._-]+)", value)
    if standalone_handle:
        return None, standalone_handle.group(1)
    custom = re.fullmatch(r"https?://(?:www\.)?youtube\.com/c/([a-zA-Z0-9._-]+)/*", value)
    if custom:
        return None, custom.group(1)
    return None, None


def _youtube():
    creds = youtube_credentials()
    if not creds:
        raise RuntimeError("YouTube OAuth connection is required for channel monitoring")
    from googleapiclient.discovery import build
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def resolve_channel(value: str) -> dict:
    channel_id, query = parse_channel_input(value)
    if not channel_id and not query:
        raise ValueError("Use a YouTube channel ID or /channel/, /@handle, or /c/ URL")
    youtube = _youtube()
    if channel_id:
        response = youtube.channels().list(part="snippet,contentDetails", id=channel_id).execute()
    else:
        response = youtube.search().list(part="snippet", q=query, type="channel", maxResults=5).execute()
        ids = [item.get("snippet", {}).get("channelId") for item in response.get("items", []) if item.get("snippet", {}).get("channelId")]
        response = youtube.channels().list(part="snippet,contentDetails", id=ids[0] if ids else "").execute()
    item = (response.get("items") or [None])[0]
    if not item:
        raise ValueError("YouTube channel was not found")
    snippet = item.get("snippet", {})
    return {"youtube_channel_id": item["id"], "channel_name": snippet.get("title") or item["id"], "channel_url": f"https://www.youtube.com/channel/{item['id']}", "thumbnail_url": snippet.get("thumbnails", {}).get("default", {}).get("url"), "uploads_playlist_id": item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")}


def monitor_channel(channel: dict) -> int:
    youtube = _youtube()
    details = youtube.channels().list(part="contentDetails", id=channel["youtube_channel_id"]).execute()
    item = (details.get("items") or [None])[0]
    playlist_id = (item or {}).get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not playlist_id:
        raise RuntimeError("Channel has no uploads playlist")
    response = youtube.playlistItems().list(part="snippet,contentDetails", playlistId=playlist_id, maxResults=settings.youtube_monitor_max_results).execute()
    detected = 0
    newest = channel.get("last_video_published_at")
    for item in response.get("items", []):
        snippet = item.get("snippet", {})
        video_id = item.get("contentDetails", {}).get("videoId")
        if not video_id or row("SELECT id FROM detected_videos WHERE youtube_video_id=?", (video_id,)):
            continue
        published = snippet.get("publishedAt")
        stamp = now()
        with connection() as con:
            con.execute("INSERT INTO detected_videos(youtube_video_id,youtube_channel_id,title,description,thumbnail_url,published_at,detected_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)", (video_id, channel["youtube_channel_id"], snippet.get("title") or video_id, snippet.get("description"), snippet.get("thumbnails", {}).get("high", snippet.get("thumbnails", {}).get("default", {})).get("url"), published, stamp, stamp, stamp))
        detected += 1
        if published and (not newest or published > newest):
            newest = published
    with connection() as con:
        con.execute("UPDATE monitored_channels SET last_checked_at=?,last_video_published_at=COALESCE(?,last_video_published_at),updated_at=? WHERE id=?", (now(), newest, now(), channel["id"]))
    return detected


def monitor_enabled_channels() -> dict:
    summary = {"checked": 0, "detected": 0, "errors": []}
    for channel in rows("SELECT * FROM monitored_channels WHERE monitoring_enabled=1 ORDER BY id"):
        summary["checked"] += 1
        try:
            summary["detected"] += monitor_channel(channel)
        except Exception as exc:
            logger.exception("Channel monitoring failed channel_id=%s", channel["youtube_channel_id"])
            summary["errors"].append({"channel_id": channel["youtube_channel_id"], "error": str(exc)})
            with connection() as con:
                con.execute("UPDATE monitored_channels SET last_checked_at=?,updated_at=? WHERE id=?", (now(), now(), channel["id"]))
    return summary


class MonitoringScheduler:
    def __init__(self):
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="youtube-monitor", daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run(self):
        interval = max(1, settings.youtube_monitor_interval_minutes) * 60
        while not self.stop_event.is_set():
            monitor_enabled_channels()
            self.stop_event.wait(interval)


monitor_scheduler = MonitoringScheduler()
