'use client'
import { ChangeEvent, useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
type Activity = { event_type: string; message: string; created_at: string }
type Dashboard = { counts: Record<string, number>; activity: Activity[] }
type Video = { id: number; filename: string; status: string; duration_seconds?: number; width?: number; height?: number }
type Moment = { id: number; start_seconds: number; end_seconds: number; title?: string; hook: string; rationale: string; category?: string; score: number; status: string }
type Clip = { id: number; video_id: number; storage_path: string; duration_seconds: number; width?: number; height?: number; title?: string; status: string }
type Service = { service_name: string; status: string; message?: string }
type Health = Record<string, { status: string; model_available?: boolean; message?: string }>
type Job = { id: number; video_id: number; kind: string; status: string; progress: number; stage?: string; message?: string; error_details?: string }
type MonitoredChannel = { id: number; youtube_channel_id: string; channel_name: string; thumbnail_url?: string; monitoring_enabled: number; last_checked_at?: string; last_video_published_at?: string }
type DetectedVideo = { id: number; youtube_video_id: string; youtube_channel_id: string; title: string; thumbnail_url?: string; published_at?: string; processing_status: string; authorized_video_id?: number; linked_job_id?: number }
type Analytics = { status: string; totals: { views: number; likes: number; comments: number; subscribers_gained: number } }
type PublicSettings = { environment: string; whisper_model: string; ollama_model: string; background_worker: boolean; max_concurrent_jobs: number; monitoring_enabled: boolean; max_upload_bytes: number }

export default function Home() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [services, setServices] = useState<Service[]>([])
  const [videos, setVideos] = useState<Video[]>([])
  const [moments, setMoments] = useState<Record<number, Moment[]>>({})
  const [clips, setClips] = useState<Clip[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [youtube, setYoutube] = useState<{ status: string; message?: string; channel?: { title?: string; id?: string } } | null>(null)
  const [monitoredChannels, setMonitoredChannels] = useState<MonitoredChannel[]>([])
  const [detectedVideos, setDetectedVideos] = useState<DetectedVideo[]>([])
  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [publicSettings, setPublicSettings] = useState<PublicSettings | null>(null)
  const [channelInput, setChannelInput] = useState('')
  const [publishVisibility, setPublishVisibility] = useState<Record<number, string>>({})
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function request(path: string, init?: RequestInit) {
    let response: Response
    try {
      response = await fetch(`${API}${path}`, init)
    } catch (cause) {
      const detail = cause instanceof Error ? cause.message : String(cause)
      throw new Error(`Cannot reach the ViralFlow backend at ${API}. Start FastAPI on port 8000 and check CORS_ORIGINS. Browser detail: ${detail}`)
    }
    const body = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(body.detail || `Backend request failed (${response.status}) at ${path}`)
    return body
  }

  async function refresh() {
    const [dashboard, integration, serviceState, videoList, clipList, jobList, connection, channelList, detectedList, analyticsState, settingsState] = await Promise.all([
      request('/api/dashboard'), request('/api/integrations'), request('/api/services'), request('/api/videos'), request('/api/clips'), request('/api/jobs'), request('/api/integrations/youtube/connection'), request('/api/youtube/channels'), request('/api/youtube/detected-videos'), request('/api/analytics'), request('/api/settings')
    ])
    setData(dashboard); setHealth(integration); setServices(serviceState); setVideos(videoList); setClips(clipList); setJobs(jobList); setYoutube(connection); setMonitoredChannels(channelList); setDetectedVideos(detectedList); setAnalytics(analyticsState); setPublicSettings(settingsState)
  }

  useEffect(() => { refresh().catch(e => setError(e.message)); const timer = window.setInterval(() => refresh().catch(() => undefined), 4000); return () => window.clearInterval(timer) }, [])

  async function run(label: string, action: () => Promise<void>) {
    setBusy(label); setError(''); setMessage('')
    try { await action(); setMessage(`${label} completed`); await refresh() } catch (e) { setError(e instanceof Error ? e.message : 'Request failed') } finally { setBusy('') }
  }

  async function upload(event: React.FormEvent) {
    event.preventDefault()
    if (!file) return setError('Choose an authorized video first')
    await run('Upload', async () => {
      const form = new FormData(); form.append('file', file)
      await request('/api/videos/upload?authorized=true', { method: 'POST', body: form })
      setFile(null)
    })
  }

  async function loadMoments(videoId: number) {
    const result = await request(`/api/videos/${videoId}/moments`)
    setMoments(previous => ({ ...previous, [videoId]: result }))
  }

  async function addChannel(event: React.FormEvent) {
    event.preventDefault()
    await run('Add channel', async () => { await request('/api/youtube/channels', { method: 'POST', body: JSON.stringify({ channel: channelInput }), headers: { 'Content-Type': 'application/json' } }); setChannelInput('') })
  }

  async function attachSource(event: ChangeEvent<HTMLInputElement>, detectedId: number) {
    const source = event.target.files?.[0]
    if (!source) return
    await run('Attach authorized source', async () => {
      const form = new FormData(); form.append('file', source)
      await request(`/api/youtube/detected-videos/${detectedId}/source?authorized=true`, { method: 'POST', body: form })
    })
  }

  async function connectYouTube() {
    await run('Start YouTube connection', async () => { const result = await request('/api/integrations/youtube/oauth/start'); window.location.href = result.authorization_url })
  }

  const cards = [['channels', 'Source channels'], ['videos', 'Imported videos'], ['jobs', 'Processing jobs'], ['moments', 'Candidate moments'], ['clips', 'Generated clips'], ['pending_approval', 'Pending approval'], ['scheduled', 'Scheduled clips'], ['published', 'Published clips'], ['failures', 'Failures']]
  return <main>
    <header><div><p className="eyebrow">VIRALFLOW AI</p><h1>Authorized video → reviewable Shorts</h1><p className="muted">Local AI workflow. Nothing is published automatically.</p></div><span className="badge">Local pipeline</span></header>
    {error && <div className="notice error">{error}</div>}
    {message && <div className="notice success">{message}</div>}
    <section className="grid">{cards.map(([key, label]) => <article className="card" key={key}><span>{label}</span><strong>{data?.counts?.[key] ?? '—'}</strong></article>)}</section>
    <section className="panel workflow"><div className="panelHead"><h2>Process an authorized video</h2><span className="muted">upload → transcribe → analyze</span></div><form onSubmit={upload} className="uploadForm"><input type="file" accept="video/*" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} /><button disabled={!file || !!busy}>{busy === 'Upload' ? 'Uploading…' : 'Upload authorized video'}</button></form><p className="muted">Only use videos you own, licensed, or are explicitly authorized to process.</p></section>
    <section className="columns"><article className="panel"><div className="panelHead"><h2>Integration health</h2><span className="muted">real checks</span></div>{health ? Object.entries(health).map(([name, value]) => <div className="health" key={name}><span>{name}<small>{value.message || ''}</small></span><span className={`status ${value.status}`}>{value.status}{value.model_available === false ? ' / model missing' : ''}</span></div>) : <p className="muted">Checking local services…</p>}</article><article className="panel"><div className="panelHead"><h2>Automation state</h2><span className="muted">backend state</span></div>{services.map(service => <div className="health" key={service.service_name}><span>{service.service_name.replaceAll('_', ' ')}<small>{service.message || ''}</small></span><span className={`status ${service.status}`}>{service.status}</span></div>)}</article></section>
    <section className="columns"><article className="panel"><div className="panelHead"><h2>YouTube connection</h2><span className="muted">official OAuth only</span></div><div className="health"><span>{youtube?.channel?.title || 'Google account'}<small>{youtube?.message || ''}</small></span><span className={`status ${youtube?.status || 'checking'}`}>{youtube?.status || 'checking'}</span></div>{youtube?.status === 'not_configured' && <p className="muted">Add Google OAuth credentials to backend/.env and restart FastAPI.</p>}{youtube?.status === 'disconnected' && <button onClick={connectYouTube}>Connect Google account</button>}</article><article className="panel"><div className="panelHead"><h2>Processing queue</h2><span className="muted">persistent jobs · auto-refresh</span></div>{jobs.length ? jobs.slice(0, 8).map(job => <div className="health" key={job.id}><span>{job.kind} #{job.id}<small>{job.stage || job.message || ''}{job.error_details ? ` · ${job.error_details}` : ''}</small></span><span className={`status ${job.status}`}>{job.status} {job.progress}% {job.status === 'failed' && <button className="secondary" onClick={() => run('Retry job', async () => { await request(`/api/jobs/${job.id}/retry`, { method: 'POST' }) })}>Retry</button>}{['pending', 'processing'].includes(job.status) && <button className="secondary" onClick={() => run('Cancel job', async () => { await request(`/api/jobs/${job.id}/cancel`, { method: 'POST' }) })}>Cancel</button>}</span></div>) : <p className="muted">No queued jobs.</p>}</article></section>
    <section className="columns"><article className="panel"><div className="panelHead"><h2>Analytics</h2><span className="muted">reported snapshots only</span></div><div className="analytics"><b>{analytics?.totals.views ?? 0}</b><span>views</span><b>{analytics?.totals.likes ?? 0}</b><span>likes</span><b>{analytics?.totals.comments ?? 0}</b><span>comments</span></div><small className="muted">Status: {analytics?.status || 'checking'}</small></article><article className="panel"><div className="panelHead"><h2>Settings</h2><span className="muted">safe runtime configuration</span></div>{publicSettings ? <div className="health"><span>{publicSettings.whisper_model} · {publicSettings.ollama_model}<small>{publicSettings.environment} · max concurrency {publicSettings.max_concurrent_jobs} · uploads {Math.round(publicSettings.max_upload_bytes / 1024 / 1024)} MB</small></span><span className={`status ${publicSettings.background_worker ? 'connected' : 'paused'}`}>worker {publicSettings.background_worker ? 'enabled' : 'disabled'}</span></div> : <p className="muted">Loading settings…</p>}</article></section>
    <section className="panel"><div className="panelHead"><h2>YouTube monitoring</h2><span className="muted">official API metadata only; no downloads</span></div><form onSubmit={addChannel} className="uploadForm"><input value={channelInput} onChange={e => setChannelInput(e.target.value)} placeholder="Channel ID, /channel/ URL, /@handle or /c/ URL" /><button disabled={!channelInput || !!busy}>Add channel</button><button type="button" className="secondary" disabled={!!busy} onClick={() => run('Monitoring check', async () => { const result = await request('/api/youtube/monitor/run', { method: 'POST' }); if (result.status !== 'completed') throw new Error(result.message || 'Monitoring did not run') })}>Check now</button></form>{monitoredChannels.length === 0 && <p className="muted">No channels configured. Connect Google OAuth, add a channel, enable monitoring, then press Check now.</p>}{monitoredChannels.map(channel => <div className="videoRow" key={channel.id}><div>{channel.thumbnail_url && <img className="thumb" src={channel.thumbnail_url} alt="" />}<b>{channel.channel_name}</b><small>{channel.youtube_channel_id} · {channel.monitoring_enabled ? 'enabled' : 'disabled'} · last checked {channel.last_checked_at || 'never'}</small></div><div className="actions"><button className="secondary" onClick={() => run('Monitoring update', async () => { await request(`/api/youtube/channels/${channel.youtube_channel_id}/monitoring`, { method: 'PATCH', body: JSON.stringify({ enabled: !channel.monitoring_enabled }), headers: { 'Content-Type': 'application/json' } }) })}>{channel.monitoring_enabled ? 'Disable' : 'Enable'}</button><button className="secondary" onClick={() => run('Remove channel', async () => { await request(`/api/youtube/channels/${channel.youtube_channel_id}`, { method: 'DELETE' }) })}>Remove</button></div></div>)}{detectedVideos.length > 0 && <div className="detectedList"><h3>Detected videos</h3>{detectedVideos.slice(0, 10).map(video => <div className="health" key={video.id}><span>{video.title}<small>{video.youtube_video_id} · {video.processing_status}</small></span><span className={`status ${video.authorized_video_id ? 'connected' : 'paused'}`}>{video.authorized_video_id ? 'source available' : 'awaiting source'}</span>{!video.authorized_video_id && <input type="file" accept="video/*" disabled={!!busy} onChange={e => attachSource(e, video.id)} />}{video.authorized_video_id && !video.linked_job_id && <button disabled={!!busy} onClick={() => run('Queue detected video', async () => { await request(`/api/youtube/detected-videos/${video.id}/process`, { method: 'POST' }) })}>Queue transcription</button>}</div>)}</div>}</section>
    <section className="panel"><div className="panelHead"><h2>Video processing</h2><span className="muted">actual database records</span></div>{videos.length ? videos.map(video => <div className="videoRow" key={video.id}><div><b>{video.filename}</b><small>{video.status} · {video.duration_seconds ? `${video.duration_seconds.toFixed(1)}s` : 'duration unknown'}</small></div><div className="actions"><button disabled={!!busy} onClick={() => run('Transcription', async () => { await request(`/api/videos/${video.id}/transcribe`, { method: 'POST', body: JSON.stringify({}), headers: { 'Content-Type': 'application/json' } }) })}>Transcribe</button><button disabled={!!busy} onClick={() => run('Qwen analysis', async () => { await request(`/api/videos/${video.id}/analyze`, { method: 'POST', body: JSON.stringify({ target_duration: 30 }), headers: { 'Content-Type': 'application/json' } }); await loadMoments(video.id) })}>Analyze moments</button><button className="secondary" onClick={() => loadMoments(video.id).catch(e => setError(e.message))}>View moments</button></div>{moments[video.id]?.map(moment => <div className="moment" key={moment.id}><div><b>{moment.title || moment.hook}</b><small>{moment.start_seconds.toFixed(1)}s–{moment.end_seconds.toFixed(1)}s · score {moment.score}/10 · {moment.category || 'general'}</small><p>{moment.rationale}</p></div><div className="actions"><button disabled={!!busy} onClick={() => run('Clip extraction', async () => { await request(`/api/moments/${moment.id}/extract`, { method: 'POST', body: JSON.stringify({ duration_seconds: 30 }), headers: { 'Content-Type': 'application/json' } }) })}>Generate clip</button></div></div>)}</div>) : <p className="muted">No videos yet.</p>}</section>
    <section className="panel"><div className="panelHead"><h2>Generated clips</h2><span className="muted">preview, subtitles, approval, publishing</span></div>{clips.length ? <div className="clipGrid">{clips.map(clip => <article className="clipCard" key={clip.id}><video controls preload="metadata" src={`${API}/api/clips/${clip.id}/file`} /><input aria-label={`Title for clip ${clip.id}`} defaultValue={clip.title || ''} placeholder="Clip title" onBlur={e => e.target.value !== (clip.title || '') && run('Save title', async () => { await request(`/api/clips/${clip.id}/metadata`, { method: 'PATCH', body: JSON.stringify({ title: e.target.value }), headers: { 'Content-Type': 'application/json' } }) })} /><small>{clip.status} · {clip.duration_seconds.toFixed(1)}s · {clip.width}×{clip.height}</small><div className="actions"><button disabled={!!busy} onClick={() => run('Subtitle generation', async () => { await request(`/api/clips/${clip.id}/subtitles?subtitle_format=srt&burn_in=true`, { method: 'POST' }) })}>Burn subtitles</button><button disabled={!!busy} onClick={() => run('Approval', async () => { await request(`/api/clips/${clip.id}/review`, { method: 'POST', body: JSON.stringify({ status: 'approved' }), headers: { 'Content-Type': 'application/json' } }) })}>Approve</button><button className="secondary" disabled={!!busy} onClick={() => run('Rejection', async () => { await request(`/api/clips/${clip.id}/review`, { method: 'POST', body: JSON.stringify({ status: 'rejected' }), headers: { 'Content-Type': 'application/json' } }) })}>Reject</button><a className="button secondary" href={`${API}/api/clips/${clip.id}/file`} download>Download</a>{['approved', 'scheduled'].includes(clip.status) && <><select value={publishVisibility[clip.id] || 'private'} onChange={e => setPublishVisibility(previous => ({ ...previous, [clip.id]: e.target.value }))}><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select><button disabled={!!busy} onClick={() => run('Publish clip', async () => { await request(`/api/clips/${clip.id}/publish`, { method: 'POST', body: JSON.stringify({ visibility: publishVisibility[clip.id] || 'private', title: clip.title }), headers: { 'Content-Type': 'application/json' } }) })}>Publish</button></>}</div></article>)}</div> : <p className="muted">Generated clips will appear here after a moment is selected.</p>}</section>
    <div className="notice"><b>Rights boundary:</b> monitoring a public channel does not grant permission to download or republish its videos.</div>
  </main>
}
