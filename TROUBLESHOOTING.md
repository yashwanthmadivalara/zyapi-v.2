# Troubleshooting

## Backend dependencies

```powershell
cd backend
..\backend\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use the project virtual environment. Faster-Whisper downloads its selected model the first time it runs.

## FFmpeg / FFprobe

Verify:

```powershell
ffmpeg -version
ffprobe -version
```

The upload requires a video and audio stream for transcription. A video-only file receives a clear validation error.

## Ollama / Qwen

Start Ollama, confirm the model is present, then test:

```powershell
Invoke-WebRequest http://127.0.0.1:11434/api/tags
ollama list
```

Set `OLLAMA_BASE_URL` and `OLLAMA_MODEL` in `backend/.env`. The API retries malformed JSON a limited number of times and records failures in `jobs` and `activity`.

Qwen analysis accepts the requested `{"moments": [...]}` wrapper, a top-level array, markdown fences, and harmless surrounding prose. It still rejects invented or out-of-range timestamps, missing transcript overlap, clips shorter than 10 seconds or longer than 65 seconds, invalid scores, and missing title/hook/explanation fields. Long transcripts are split into timestamp-preserving chunks.

## Processing failures

Check `/api/videos/{video_id}/status` for the video state, job messages, moments, and clips. Retry transcription or analysis with `POST /api/videos/{video_id}/retry` and JSON `{"kind":"transcription"}` or `{"kind":"analysis"}`.

## Frontend “Failed to fetch”

This browser message means the frontend could not complete a network request; it is not an Ollama error. Confirm that `http://127.0.0.1:8000/health` returns JSON, then restart the backend after changing `.env`. `CORS_ORIGINS` must include the exact frontend origin, including `localhost` versus `127.0.0.1` and the port. The dashboard now reports the backend URL and startup/CORS guidance instead of exposing only the generic browser message.

## Resource limits

The default Whisper configuration is CPU/INT8. Use the `tiny` model for a quick smoke test and `base` for better quality after confirming memory and processing time on the laptop. Set `ENABLE_BACKGROUND_WORKER=true` to enable the durable single-concurrency worker. Uploaded authorized videos then create a `pipeline` job automatically; inspect `/api/jobs` or the dashboard for stage, progress, and errors.
