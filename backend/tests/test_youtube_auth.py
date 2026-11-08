from urllib.parse import parse_qs, urlparse

from app.config import settings
from app.youtube_auth import authorization_url


def test_authorization_url_contains_configured_redirect_uri(monkeypatch):
    monkeypatch.setattr(settings, "youtube_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(settings, "youtube_client_secret", "test-secret")
    monkeypatch.setattr(settings, "youtube_redirect_uri", "http://localhost:8000/api/integrations/youtube/oauth/callback")
    query = parse_qs(urlparse(authorization_url()).query)
    assert query["redirect_uri"] == [settings.youtube_redirect_uri]
