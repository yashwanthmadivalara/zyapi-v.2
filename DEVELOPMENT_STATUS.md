# ViralFlow AI development status

## Current milestone

The local AI video-processing path is operational through subtitle burn-in and preview retrieval:

`authorized upload → FFprobe → FFmpeg audio extraction → Faster-Whisper → Ollama/Qwen analysis → validated moments → vertical FFmpeg clip → SRT → burned-in subtitles → preview`

## Implemented in this milestone

- Faster-Whisper CPU/INT8 transcription with language detection and timestamped segments.
- Ollama `qwen2.5:3b` analysis with JSON parsing, limited retries, timestamp alignment, range checks, and overlap filtering.
- Persisted AI candidate fields: title, hook, explanation, category, caption, score, and timestamps.
- FFmpeg clip validation for dimensions, duration, video stream, and source audio preservation.
- SRT generation and FFmpeg burned-in subtitles.
- Processing status, job records, retry endpoints, preview endpoint, and frontend workflow controls.
- Persistent SQLite job queue with deduplication, restart recovery, cancellation, retry, and opt-in single-worker processing for the complete pipeline.
- Google OAuth start/callback/connection/disconnect boundary using official Google libraries; live credentials are still required for verification.
- YouTube monitoring foundation: official API channel resolution, persistent monitored/detected tables, duplicate-safe uploads-playlist polling, opt-in scheduler, authorized-source association, and transcription queue handoff.
- Monitoring dashboard controls for adding/removing channels, enabling checks, viewing metadata, attaching an authorized local source, and queueing transcription.
- Complete opt-in background `pipeline` job from upload through transcription, Qwen analysis, clip extraction, SRT generation, burned subtitles, validation, and approval-ready clips, with stage progress, cooperative cancellation, retry support, and output reuse on recovery.
- Explicit approval-gated YouTube publishing with resumable official API upload, privacy selection, editable metadata, duplicate-publish protection, publishing event records, and mocked upload tests; real-account publishing remains unverified.
- Qwen analysis reliability improved with wrapper/fence/prose-tolerant JSON parsing, strict alias-aware timestamp validation, transcript chunking with preserved timestamps, non-identical corrective retries, and diagnostic logging. Real local Qwen analysis now passes.
- Integration health and monitoring feedback now explain disabled/configuration-required states, including Faster-Whisper package availability, Google OAuth requirements, monitoring-disabled state, no configured channels, and monitoring API errors.

## Deliberately not in this milestone

Real Google OAuth/publishing, live channel monitoring, analytics collection, cloud deployment, and daemon-thread stress testing remain unverified or incomplete.
