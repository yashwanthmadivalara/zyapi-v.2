# ViralFlow AI test results

Date: 2026-11-08

## Automated tests

Run with:

```powershell
$env:PYTHONPATH='backend'
backend\.venv\Scripts\python.exe -m pytest backend/tests -q --basetemp=tmp\pytest
```

The backend suite currently reports 19 passed and 4 skipped in the project virtual environment. Integration tests are marked and require `VIRALFLOW_TEST_VIDEO`.

## Real integrations verified

- Faster-Whisper: passed against `How to Create Stickman Stand Up Videos.mp4`; English transcript persisted with 12 timestamped segments.
- Ollama/Qwen: passed with local `qwen2.5:3b`; validated moments persisted with timestamps and quality fields.
- FFmpeg/FFprobe: passed for audio extraction, vertical clip generation, stream/duration/dimension validation, SRT generation, subtitle burn-in, and preview retrieval.
- Frontend: `npm run build` passed.
- Queue unit tests: deduplication and restart recovery passed.
- YouTube monitoring unit tests: channel-input parsing, scheduler summary/error boundary, official-client-shaped polling, and duplicate video prevention passed.
- Complete worker pipeline test passed with mocked AI/FFmpeg stages, including stage progression and recovery-safe output reuse.
- Complete worker pipeline passed with the authorized local video `How to Create Stickman Stand Up Videos.mp4`; Faster-Whisper, Ollama/Qwen, FFmpeg clip extraction, SRT generation, burned subtitles, validation, and database status completion were verified in one isolated run (4m 12s).
- Clip preview/download now prefers the validated burned-subtitle output when it exists and otherwise serves the generated clip.
- Mocked YouTube publishing test passed: rejected clips were blocked, approved clips used resumable upload, privacy metadata was sent, and remote ID/URL were persisted.
- Qwen analysis fix: 9 focused parser/validation/chunking/retry tests passed; real authorized-video Qwen integration passed with `qwen2.5:3b` in 3m 43s.
- Ollama connectivity check: `GET http://127.0.0.1:11434/api/tags` returned HTTP 200 and listed `qwen2.5:3b`; no reinstall or model download was performed.
- Frontend/backend verification repeated twice: backend suite passed 19/19 on both rounds; frontend production build passed twice; API smoke endpoints returned HTTP 200.
- Monitoring manual-run smoke test now returns an explicit `no_channels` message instead of appearing to do nothing.
- OAuth code is present but not tested against a real Google account; credential-free tests remain required.
- Live channel resolution, live uploads-playlist polling, and the background scheduler remain unverified because Google OAuth credentials were not available.
- The real test invoked the same `JobWorker` execution path in isolation rather than starting the FastAPI daemon worker thread; daemon startup and shutdown remain covered by code and unit-level behavior, but are not separately stress-tested.

## Known warnings

- FastAPI's existing `on_event` startup hook is deprecated but still functional.
- Next.js 14.2.21 reports a dependency security advisory during `npm install`; upgrading it is a separate maintenance task.
- YouTube OAuth and live monitoring are not configured in the current `backend/.env`; this is an external Google credential requirement, not an application crash.
