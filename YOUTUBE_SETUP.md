# YouTube setup

ViralFlow AI uses official Google OAuth and YouTube Data API v3 only. It never downloads videos from monitored channels.

1. Create or select a Google Cloud project.
2. Enable YouTube Data API v3.
3. Configure an OAuth consent screen for the local app.
4. Create a Web application OAuth client with redirect URI:
   `http://localhost:8000/api/integrations/youtube/oauth/callback`
5. Copy the client ID and secret into the backend-only `.env` file:

```text
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/integrations/youtube/oauth/callback
YOUTUBE_TOKEN_PATH=./data/youtube-token.json
```

6. Start the backend and call `GET /api/integrations/youtube/oauth/start` from the local dashboard flow.
7. Complete Google consent. The callback stores the token locally and never returns it to browser code.
8. Check `GET /api/integrations/youtube/connection` before publishing.

Publishing still requires an explicit approved clip. Use a private visibility upload first. Do not commit `.env` or `youtube-token.json`.

Automated tests use mocked Google clients and do not require real credentials. A real OAuth or upload result must not be reported as verified until it is tested with the user’s account.
