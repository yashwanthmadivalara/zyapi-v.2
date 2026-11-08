import json
import logging
import secrets
import time
from pathlib import Path

from .config import settings

logger = logging.getLogger("viralflow.youtube_auth")
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/youtube.upload"]
_states: dict[str, float] = {}


def configured() -> bool:
    return bool(settings.youtube_client_id and settings.youtube_client_secret)


def _flow(state: str | None = None):
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_config({"web": {"client_id": settings.youtube_client_id, "client_secret": settings.youtube_client_secret, "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": [settings.youtube_redirect_uri]}}, scopes=SCOPES, state=state)
    # google-auth-oauthlib does not reliably copy the configured redirect URI
    # into the authorization request from redirect_uris alone. Set it explicitly
    # so Google's request contains redirect_uri and the callback uses the same value.
    flow.redirect_uri = settings.youtube_redirect_uri
    return flow


def authorization_url() -> str:
    if not configured():
        raise RuntimeError("YouTube OAuth client credentials are not configured")
    state = secrets.token_urlsafe(32)
    _states[state] = time.time() + 600
    flow = _flow(state)
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    return url


def complete_callback(state: str, code: str) -> dict:
    expiry = _states.pop(state, None)
    if not expiry or expiry < time.time():
        raise RuntimeError("OAuth state is missing or expired")
    flow = _flow(state)
    flow.fetch_token(code=code)
    path = Path(settings.youtube_token_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(flow.credentials.to_json(), encoding="utf-8")
    return {"status": "connected", "token_path": str(path)}


def credentials():
    if not Path(settings.youtube_token_path).is_file():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    creds = Credentials.from_authorized_user_file(settings.youtube_token_path, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        Path(settings.youtube_token_path).write_text(creds.to_json(), encoding="utf-8")
    return creds if creds.valid else None


def disconnect() -> None:
    Path(settings.youtube_token_path).unlink(missing_ok=True)
