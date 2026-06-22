import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Mic, MicOff, Send, Paperclip, Volume2, VolumeX,
  Trash2, Plus, FileText, Calendar, Battery, Clock, X, Copy, Check
} from 'lucide-react';
import './App.css';

/* ─────────────────────────────────────────────
   Constants
───────────────────────────────────────────── */
const API_BASE = '/api/v1';

function getWebSocketUrl(path) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${path}`;
}

const VOICE_STATE_CONFIG = {
  idle:          { label: 'VOICE READY' },
  listening:     { label: 'LISTENING…' },
  wake_detected: { label: 'WAKE DETECTED' },
  processing:    { label: 'PROCESSING…' },
  speaking:      { label: 'MITRA SPEAKING' },
  error:         { label: 'SYSTEM ERROR' },
};

/* ─────────────────────────────────────────────
   SoundFX — Web Audio API synthesizer
   (no external files, no backend calls)
───────────────────────────────────────────── */
const SoundFX = (() => {
  let ctx = null;
  const getCtx = () => {
    if (!ctx) ctx = new (window.AudioContext || window.webkitAudioContext)();
    return ctx;
  };

  const playTone = (freq, type, duration, volume = 0.06, delay = 0) => {
    try {
      const ac = getCtx();
      const osc = ac.createOscillator();
      const gain = ac.createGain();
      osc.connect(gain);
      gain.connect(ac.destination);
      osc.type = type;
      osc.frequency.setValueAtTime(freq, ac.currentTime + delay);
      gain.gain.setValueAtTime(0, ac.currentTime + delay);
      gain.gain.linearRampToValueAtTime(volume, ac.currentTime + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + delay + duration);
      osc.start(ac.currentTime + delay);
      osc.stop(ac.currentTime + delay + duration);
    } catch (e) { /* audio blocked — ignore */ }
  };

  return {
    playBoot() {
      playTone(220, 'sine', 0.3, 0.05, 0.0);
      playTone(330, 'sine', 0.3, 0.05, 0.12);
      playTone(440, 'sine', 0.4, 0.06, 0.24);
      playTone(660, 'sine', 0.5, 0.07, 0.38);
    },
    playSend() {
      playTone(800, 'sine', 0.08, 0.04);
      playTone(1000, 'sine', 0.06, 0.03, 0.05);
    },
    playComplete() {
      playTone(523, 'sine', 0.2, 0.05, 0.0);
      playTone(659, 'sine', 0.3, 0.05, 0.15);
    },
    playError() {
      playTone(200, 'sawtooth', 0.15, 0.05, 0.0);
      playTone(180, 'sawtooth', 0.2, 0.04, 0.1);
    },
    playClick() {
      playTone(1200, 'square', 0.04, 0.03);
    },
  };
})();

/* ─────────────────────────────────────────────
   Particle Background
───────────────────────────────────────────── */
function ParticleBackground({ voiceState }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let raf;
    let w = (canvas.width = window.innerWidth);
    let h = (canvas.height = window.innerHeight);

    const onResize = () => {
      w = canvas.width = window.innerWidth;
      h = canvas.height = window.innerHeight;
    };
    window.addEventListener('resize', onResize);

    // State color map — matches the orb spec
    const colorMap = {
      idle:          { r: 0,   g: 136, b: 255 },
      listening:     { r: 0,   g: 255, b: 136 },
      wake_detected: { r: 0,   g: 255, b: 136 },
      processing:    { r: 255, g: 204, b: 0   },
      speaking:      { r: 187, g: 0,   b: 255 },
      error:         { r: 255, g: 34,  b: 34  },
    };

    const target = colorMap[voiceState] || colorMap.idle;
    const cur = { ...target };
    const COUNT = 60;
    const pts = Array.from({ length: COUNT }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.22,
      vy: (Math.random() - 0.5) * 0.22,
      r: Math.random() * 1.8 + 0.6,
      a: Math.random() * 0.35 + 0.08,
    }));

    const draw = () => {
      ctx.clearRect(0, 0, w, h);
      cur.r += (target.r - cur.r) * 0.035;
      cur.g += (target.g - cur.g) * 0.035;
      cur.b += (target.b - cur.b) * 0.035;
      const R = Math.round(cur.r), G = Math.round(cur.g), B = Math.round(cur.b);

      pts.forEach(p => {
        p.x = (p.x + p.vx + w) % w;
        p.y = (p.y + p.vy + h) % h;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        if (p.r > 1.4) { ctx.shadowBlur = 10; ctx.shadowColor = `rgb(${R},${G},${B})`; }
        else ctx.shadowBlur = 0;
        ctx.fillStyle = `rgba(${R},${G},${B},${p.a})`;
        ctx.fill();
      });
      ctx.shadowBlur = 0;

      // Constellation lines
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const d = Math.hypot(pts[i].x - pts[j].x, pts[i].y - pts[j].y);
          if (d < 85) {
            ctx.beginPath();
            ctx.moveTo(pts[i].x, pts[i].y);
            ctx.lineTo(pts[j].x, pts[j].y);
            ctx.strokeStyle = `rgba(${R},${G},${B},${(1 - d / 85) * 0.055})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        }
      }
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => { window.removeEventListener('resize', onResize); cancelAnimationFrame(raf); };
  }, [voiceState]);

  return <canvas ref={canvasRef} className="particle-canvas" />;
}

/* ─────────────────────────────────────────────
   Cinematic Boot Screen
───────────────────────────────────────────── */
const BOOT_MODULES = [
  { label: 'Neural Core v1.0',          key: 'neural'  },
  { label: 'Speech Recognition Engine', key: 'stt'     },
  { label: 'Voice Synthesis (ElevenLabs)', key: 'tts'  },
  { label: 'SQLite Database Link',       key: 'db'      },
  { label: 'Gemini AI Cognitive Engine', key: 'ai'      },
  { label: 'Wake-Word Listener',         key: 'wake'    },
  { label: 'WebSocket Gateway',          key: 'ws'      },
];

function BootScreen({ onComplete }) {
  const [doneModules, setDoneModules] = useState([]);
  const [progress, setProgress] = useState(0);
  const [fade, setFade] = useState(false);
  // Guard so finish() can only fire once even if intervals race
  const finishedRef = useRef(false);

  const finish = useCallback(() => {
    if (finishedRef.current) return;
    finishedRef.current = true;
    SoundFX.playBoot();
    setFade(true);
    // Match the CSS transition duration exactly (700ms) so the overlay
    // is fully invisible before React unmounts it and mounts the dashboard.
    setTimeout(onComplete, 750);
  }, [onComplete]);

  useEffect(() => {
    let idx = 0;
    const modInterval = setInterval(() => {
      if (idx < BOOT_MODULES.length) {
        setDoneModules(prev => [...prev, BOOT_MODULES[idx].key]);
        idx++;
      } else {
        clearInterval(modInterval);
      }
    }, 260);

    const progInterval = setInterval(() => {
      setProgress(prev => {
        const next = prev + Math.random() * 7 + 3;
        if (next >= 100) {
          clearInterval(progInterval);
          setTimeout(finish, 250);
          return 100;
        }
        return next;
      });
    }, 90);

    return () => { clearInterval(modInterval); clearInterval(progInterval); };
  }, [finish]);

  return (
    <div className={`boot-overlay${fade ? ' fade-out' : ''}`}>
      <div className="boot-container">
        <div className="boot-scanner">
          <div className="scanner-ring" />
          <div className="scanner-laser" />
          <div className="scanner-core" />
        </div>

        <div className="boot-eyebrow">SYSTEM INITIALIZATION</div>
        <div className="boot-title">
          MITRA <span>AI SYSTEM</span> v1.0
        </div>

        <div className="boot-modules">
          {BOOT_MODULES.map((mod, i) => {
            const done = doneModules.includes(mod.key);
            const active = doneModules.length === i;
            return (
              <div
                key={mod.key}
                className="boot-module-row"
                style={{ animationDelay: `${i * 0.05}s`, opacity: done || active ? 1 : 0.25 }}
              >
                <div className={`boot-module-icon ${done ? 'ok' : 'loading'}`}>
                  {done ? '✓' : ''}
                </div>
                <span className="boot-module-label">{mod.label}</span>
                <span className={`boot-module-status ${done ? 'ok' : 'wait'}`}>
                  {done ? 'ONLINE' : 'LOADING…'}
                </span>
              </div>
            );
          })}
        </div>

        <div className="boot-progress-bar">
          <div className="boot-progress-fill" style={{ width: `${Math.min(progress, 100)}%` }} />
        </div>
        <div className="boot-progress-text">{Math.min(Math.floor(progress), 100)}% INITIALIZED</div>

        <button
          className="neon-border-btn boot-bypass-btn"
          onClick={() => { if (!finishedRef.current) { finishedRef.current = true; setFade(true); setTimeout(onComplete, 450); } }}
        >
          SKIP BOOT SEQUENCE
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   MITRA Orb Component — 5 states
───────────────────────────────────────────── */
function MitraOrb({ voiceState, isRecording, isTyping, recordingStatus, voiceStateText }) {
  const state = (() => {
    if (voiceState !== 'idle') return voiceState;
    if (isRecording) return 'listening';
    if (isTyping)    return 'processing';
    return 'idle';
  })();

  const label = (() => {
    if (state === 'listening' || state === 'wake_detected') return 'LISTENING ACTIVE';
    if (state === 'processing') return 'AI THINKING…';
    if (state === 'speaking')   return 'MITRA SPEAKING';
    if (state === 'error')      return 'DIAGNOSTIC FAULT';
    if (isRecording)            return 'VOICE CAPTURE';
    return 'COGNITIVE CORE';
  })();

  return (
    <div className={`orb-wrapper state-${state}`}>
      {/* Multi-ring scanner */}
      <div className="orb-scanner-rings">
        <div className="orb-ring ring-pulse" />
        <div className="orb-ring ring-outer" />
        <div className="orb-ring ring-middle" />
        <div className="orb-ring ring-inner" />
      </div>

      {/* Glowing core */}
      <div className="orb-core-container">
        <div className="orb-core">
          {state === 'listening' && (
            <div className="orb-waves">
              <div className="orb-wave" /><div className="orb-wave" /><div className="orb-wave" />
            </div>
          )}
          {state === 'wake_detected' && (
            <div className="orb-waves">
              <div className="orb-wave" /><div className="orb-wave" /><div className="orb-wave" />
            </div>
          )}
          {state === 'speaking' && (
            <div className="orb-audio-spectrum">
              {[...Array(6)].map((_, i) => <div key={i} className="spec-bar" />)}
            </div>
          )}
          {state === 'processing' && (
            <>
              <div className="orb-thinking-nebula" />
              <div className="orb-thinking-nebula-2" />
            </>
          )}
          {state === 'error' && (
            <div className="orb-error-flicker">
              <div className="error-symbol">!</div>
            </div>
          )}
        </div>
      </div>

      {/* Labels below rings */}
      <div className="orb-details">
        <div className="orb-label">{label}</div>
        {voiceState !== 'idle' && voiceStateText && (
          <div className="orb-subtext">{voiceStateText}</div>
        )}
        {isRecording && voiceState === 'idle' && (
          <div className="orb-subtext">{recordingStatus}</div>
        )}
        {state === 'idle' && (
          <div className="orb-subtext blink-slow">SAY "MITRA" TO AWAKEN</div>
        )}
      </div>

      {/* Dynamic Status Indicators */}
      <StatusIndicators voiceState={voiceState} isTyping={isTyping} isRecording={isRecording} />
    </div>
  );
}

/* ─────────────────────────────────────────────
   Dynamic Status Indicators
───────────────────────────────────────────── */
function StatusIndicators({ voiceState, isTyping, isRecording }) {
  const listening = voiceState === 'listening' || voiceState === 'wake_detected' || isRecording;
  const thinking  = voiceState === 'processing' || isTyping;
  const speaking  = voiceState === 'speaking';
  const memory    = true; // session always active

  const pills = [
    { label: 'VOICE LISTENING', active: listening, rgb: 'var(--orb-listen-rgb)' },
    { label: 'AI THINKING',     active: thinking,  rgb: 'var(--orb-think-rgb)'  },
    { label: 'AI SPEAKING',     active: speaking,  rgb: 'var(--orb-speak-rgb)'  },
    { label: 'MEMORY ACTIVE',   active: memory,    rgb: 'var(--primary-glow-rgb)' },
  ];

  return (
    <div className="status-indicators">
      {pills.map(p => (
        <div
          key={p.label}
          className={`status-pill${p.active ? ' active' : ''}`}
          style={{ '--pill-rgb': p.rgb }}
        >
          <div className="status-pill-dot" />
          {p.label}
        </div>
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Code Block Card with copy button
───────────────────────────────────────────── */
function CodeBlockCard({ lang, code }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      SoundFX.playClick();
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div className="code-block-card">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || 'code'}</span>
        <button className={`code-block-copy${copied ? ' copied' : ''}`} onClick={copy}>
          {copied ? '✓ COPIED' : 'COPY'}
        </button>
      </div>
      <div className="code-block-body">
        <code>{code}</code>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Message Renderer — parses markdown + code blocks
───────────────────────────────────────────── */
function MessageContent({ text }) {
  if (!text) return null;

  // Split on triple-backtick code blocks
  const segments = [];
  const codeRe = /```(\w*)\n?([\s\S]*?)```/g;
  let last = 0, m;
  while ((m = codeRe.exec(text)) !== null) {
    if (m.index > last) segments.push({ type: 'text', content: text.slice(last, m.index) });
    segments.push({ type: 'code', lang: m[1], content: m[2].trim() });
    last = m.index + m[0].length;
  }
  if (last < text.length) segments.push({ type: 'text', content: text.slice(last) });

  return (
    <>
      {segments.map((seg, i) => {
        if (seg.type === 'code') {
          return <CodeBlockCard key={i} lang={seg.lang} code={seg.content} />;
        }
        // Inline markdown for text segments
        let html = seg.content
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
          .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
          .replace(/\*(.+?)\*/g, '<em>$1</em>')
          .replace(/`([^`\n]+?)`/g, '<code>$1</code>')
          .replace(/^### (.+)$/gm, '<h3>$1</h3>')
          .replace(/^## (.+)$/gm, '<h2>$1</h2>')
          .replace(/^# (.+)$/gm, '<h1>$1</h1>')
          .replace(/^\s*[-*+]\s+(.+)$/gm, '<li>$1</li>')
          .replace(/\n/g, '<br />');
        return <div key={i} className="chat-content" dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </>
  );
}

/* ─────────────────────────────────────────────
   Chat Bubble
───────────────────────────────────────────── */
function ChatBubble({ msg }) {
  const [copied, setCopied] = useState(false);

  const copyMsg = () => {
    navigator.clipboard.writeText(msg.text).then(() => {
      setCopied(true);
      SoundFX.playClick();
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`chat-bubble ${msg.sender}`}>
      <div className="bubble-header">
        <span className="bubble-sender">
          {msg.sender === 'user' ? 'YOU' : 'MITRA CORE'} · {msg.timestamp}
        </span>
        <div className="bubble-actions">
          {msg.text && (
            <button className={`bubble-copy-btn${copied ? ' copied' : ''}`} onClick={copyMsg}>
              {copied ? <><Check size={10} /> COPIED</> : <><Copy size={10} /> COPY</>}
            </button>
          )}
        </div>
      </div>

      <MessageContent text={msg.text} />

      {msg.isStreaming && <span className="streaming-cursor" />}

      {msg.fileAttached && (
        <div style={{
          marginTop: 10, padding: '5px 10px',
          border: '1px solid rgba(0,200,255,0.2)',
          background: 'rgba(0,200,255,0.04)',
          color: 'var(--primary-glow)',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.73rem', borderRadius: 6,
          display: 'inline-flex', alignItems: 'center', gap: 6,
        }}>
          <FileText size={12} /> {msg.fileAttached}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main App
───────────────────────────────────────────── */
export default function App() {
  const [isBooted, setIsBooted] = useState(false);

  // Chat
  const [messages, setMessages] = useState([{
    sender: 'assistant',
    text: 'System online. Hello, I am MITRA — your AI assistant. How can I help?',
    timestamp: new Date().toLocaleTimeString(),
  }]);
  const [inputText, setInputText]     = useState('');
  const [sessionId, setSessionId]     = useState('');
  const [isTyping, setIsTyping]       = useState(false);
  const [voiceOutput, setVoiceOutput] = useState(true);
  const [attachedFile, setAttachedFile] = useState(null);
  const [uploading, setUploading]     = useState(false);

  // Char-by-char streaming buffer
  const streamBufferRef = useRef('');
  const streamTimerRef  = useRef(null);
  const displayedRef    = useRef('');

  // Recording
  const [isRecording, setIsRecording] = useState(false);
  const [recordingStatus, setRecordingStatus] = useState('Idle');
  const mediaRecorderRef = useRef(null);
  const audioChunksRef   = useRef([]);

  // Voice-state WS
  const [voiceState, setVoiceState]       = useState('idle');
  const [voiceStateText, setVoiceStateText] = useState('');
  const voiceWsRef = useRef(null);

  // System stats
  const [systemStats, setSystemStats] = useState({
    cpu_percent: 0, ram_percent: 0, ram_used_gb: 0, ram_total_gb: 0,
    battery_percent: 100, battery_plugged: true,
    disk_percent: 0, uptime_seconds: 0,
  });
  const [tasks, setTasks]         = useState([]);
  const [notes, setNotes]         = useState([]);
  const [reminders, setReminders] = useState([]);

  // Forms
  const [activeForm, setActiveForm]       = useState('task');
  const [taskTitle, setTaskTitle]         = useState('');
  const [taskDue, setTaskDue]             = useState('');
  const [noteTitle, setNoteTitle]         = useState('');
  const [noteContent, setNoteContent]     = useState('');
  const [reminderTitle, setReminderTitle] = useState('');
  const [reminderAt, setReminderAt]       = useState('');

  const wsRef      = useRef(null);
  const chatEndRef = useRef(null);
  const audioRef   = useRef(null);

  /* ── Voice-state WS ── */
  const connectVoiceStateWs = useCallback(() => {
    const ws = new WebSocket(getWebSocketUrl('/ws/voice-state'));
    voiceWsRef.current = ws;
    ws.onmessage = evt => {
      try {
        const d = JSON.parse(evt.data);
        if (d.type === 'voice_state') { setVoiceState(d.state || 'idle'); setVoiceStateText(d.text || ''); }
      } catch {}
    };
    ws.onclose = () => setTimeout(() => document.visibilityState !== 'hidden' && connectVoiceStateWs(), 3000);
  }, []);

  /* ── Init ── */
  useEffect(() => {
    setSessionId(Math.random().toString(36).slice(2, 15));
    fetchSystemStats(); fetchTasks(); fetchNotes(); fetchReminders();
    const si = setInterval(fetchSystemStats, 4000);
    const di = setInterval(() => { fetchTasks(); fetchNotes(); fetchReminders(); }, 10000);
    connectVoiceStateWs();
    return () => { clearInterval(si); clearInterval(di); wsRef.current?.close(); voiceWsRef.current?.close(); };
  }, [connectVoiceStateWs]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, isTyping]);

  /* ── Fetch utils ── */
  const fetchSystemStats = async () => {
    try { const r = await fetch(`${API_BASE}/system/stats`); if (r.ok) setSystemStats(await r.json()); } catch {}
  };
  const fetchTasks     = async () => { try { const r = await fetch(`${API_BASE}/tasks/`);     if (r.ok) setTasks(await r.json());     } catch {} };
  const fetchNotes     = async () => { try { const r = await fetch(`${API_BASE}/notes/`);     if (r.ok) setNotes(await r.json());     } catch {} };
  const fetchReminders = async () => { try { const r = await fetch(`${API_BASE}/reminders/`); if (r.ok) setReminders(await r.json()); } catch {} };

  /* ── File Upload ── */
  const handleFileChange = async e => {
    const file = e.target.files[0]; if (!file) return;
    setUploading(true);
    const fd = new FormData(); fd.append('file', file);
    try {
      const r = await fetch(`${API_BASE}/files/upload`, { method: 'POST', body: fd });
      if (r.ok) setAttachedFile(await r.json());
    } catch {} finally { setUploading(false); }
  };

  /* ── Recording ── */
  const startRecording = async () => {
    audioChunksRef.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      mr.ondataavailable = e => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = async () => {
        setRecordingStatus('Transcribing…');
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        stream.getTracks().forEach(t => t.stop());
        const fd = new FormData(); fd.append('file', blob, 'voice_input.webm');
        try {
          const r = await fetch(`${API_BASE}/speech/stt`, { method: 'POST', body: fd });
          if (r.ok) { const d = await r.json(); if (d.text?.trim()) setInputText(d.text); }
        } catch {} finally { setIsRecording(false); setRecordingStatus('Idle'); }
      };
      mr.start(); setIsRecording(true); setRecordingStatus('Recording…');
    } catch { setIsRecording(false); }
  };
  const stopRecording = () => mediaRecorderRef.current?.stop();

  /* ── TTS ── */
  const speak = async text => {
    if (!voiceOutput) return;
    try {
      const r = await fetch(`${API_BASE}/speech/tts`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice: 'auq43ws1oslv0tO4BDa7' }),
      });
      if (r.ok) {
        const url = URL.createObjectURL(await r.blob());
        if (audioRef.current) { audioRef.current.src = url; audioRef.current.play().catch(() => {}); }
      }
    } catch {}
  };

  /* ── Char-by-char streaming drain ── */
  const startStreamDrain = useCallback((msgIndex) => {
    if (streamTimerRef.current) clearInterval(streamTimerRef.current);
    displayedRef.current = '';

    streamTimerRef.current = setInterval(() => {
      const buf = streamBufferRef.current;
      const displayed = displayedRef.current;
      if (displayed.length >= buf.length) return;

      // Drain faster if buffer is growing large
      const lag = buf.length - displayed.length;
      const step = lag > 40 ? 6 : lag > 15 ? 3 : 1;
      const next = displayed + buf.slice(displayed.length, displayed.length + step);
      displayedRef.current = next;

      setMessages(prev => {
        const list = [...prev];
        if (list[msgIndex]?.isStreaming) list[msgIndex] = { ...list[msgIndex], text: next };
        return list;
      });
    }, 18); // ~55 chars/sec
  }, []);

  const stopStreamDrain = () => {
    if (streamTimerRef.current) { clearInterval(streamTimerRef.current); streamTimerRef.current = null; }
  };

  /* ── Send message ── */
  const handleSendText = e => {
    if (e) e.preventDefault();
    const msg = inputText.trim();
    if (!msg && !attachedFile) return;

    const userMsg   = inputText;
    const curFile   = attachedFile;
    const ts        = new Date().toLocaleTimeString();
    const aiMsgIdx  = messages.length + 1; // will be after user msg

    setMessages(prev => [
      ...prev,
      { sender: 'user', text: userMsg, fileAttached: curFile?.filename, timestamp: ts },
      { sender: 'assistant', text: '', timestamp: ts, isStreaming: true },
    ]);
    setInputText(''); setAttachedFile(null); setIsTyping(true);
    SoundFX.playSend();

    streamBufferRef.current = '';
    displayedRef.current    = '';
    startStreamDrain(aiMsgIdx);

    const socket = new WebSocket(getWebSocketUrl('/ws/chat'));
    wsRef.current = socket;
    let didConnect = false;

    socket.onopen = () => {
      didConnect = true;
      socket.send(JSON.stringify({ message: userMsg, session_id: sessionId, file_path: curFile?.filepath ?? null }));
    };

    socket.onmessage = evt => {
      const data = JSON.parse(evt.data);
      if (data.type === 'chunk') {
        streamBufferRef.current += data.content;
      } else if (data.type === 'done') {
        // Flush any remaining buffer instantly
        setTimeout(() => {
          stopStreamDrain();
          const finalText = streamBufferRef.current;
          setMessages(prev => {
            const list = [...prev];
            if (list[aiMsgIdx]?.isStreaming) list[aiMsgIdx] = { ...list[aiMsgIdx], text: finalText, isStreaming: false };
            return list;
          });
          setIsTyping(false);
          SoundFX.playComplete();
          speak(finalText);
          setTimeout(() => { fetchTasks(); fetchNotes(); fetchReminders(); }, 800);
        }, 350); // slight delay to let drain catch up
        socket.close();
      } else if (data.type === 'error') {
        stopStreamDrain();
        setMessages(prev => {
          const list = [...prev];
          if (list[aiMsgIdx]) list[aiMsgIdx] = { ...list[aiMsgIdx], text: `[Error] ${data.content}`, isStreaming: false };
          return list;
        });
        setIsTyping(false);
        SoundFX.playError();
        socket.close();
      }
    };

    socket.onclose = evt => {
      if (!didConnect && evt.code !== 1000) {
        stopStreamDrain();
        setIsTyping(false);
        setMessages(prev => {
          const list = [...prev];
          if (list[aiMsgIdx]?.isStreaming) list[aiMsgIdx] = { ...list[aiMsgIdx], text: '[Connection failed]', isStreaming: false };
          return list;
        });
      }
    };
    socket.onerror = () => {};
  };

  /* ── CRUD ── */
  const handleAddTask = async e => {
    e.preventDefault(); if (!taskTitle.trim()) return;
    SoundFX.playClick();
    try {
      const r = await fetch(`${API_BASE}/tasks/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: taskTitle, due_date: taskDue || null }) });
      if (r.ok) { setTaskTitle(''); setTaskDue(''); fetchTasks(); }
    } catch {}
  };
  const handleToggleTask = async task => {
    SoundFX.playClick();
    try { const r = await fetch(`${API_BASE}/tasks/${task.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status: task.status === 'pending' ? 'done' : 'pending' }) }); if (r.ok) fetchTasks(); } catch {}
  };
  const handleDeleteTask    = async id => { SoundFX.playClick(); try { await fetch(`${API_BASE}/tasks/${id}`,    { method: 'DELETE' }); fetchTasks();     } catch {} };
  const handleAddNote       = async e => {
    e.preventDefault(); if (!noteTitle.trim()) return; SoundFX.playClick();
    try { const r = await fetch(`${API_BASE}/notes/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: noteTitle, content: noteContent }) }); if (r.ok) { setNoteTitle(''); setNoteContent(''); fetchNotes(); } } catch {}
  };
  const handleDeleteNote    = async id => { SoundFX.playClick(); try { await fetch(`${API_BASE}/notes/${id}`,    { method: 'DELETE' }); fetchNotes();     } catch {} };
  const handleAddReminder   = async e => {
    e.preventDefault(); if (!reminderTitle.trim() || !reminderAt) return; SoundFX.playClick();
    try { const r = await fetch(`${API_BASE}/reminders/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: reminderTitle, remind_at: reminderAt.replace('T', ' ') }) }); if (r.ok) { setReminderTitle(''); setReminderAt(''); fetchReminders(); } } catch {}
  };
  const handleDeleteReminder = async id => { SoundFX.playClick(); try { await fetch(`${API_BASE}/reminders/${id}`, { method: 'DELETE' }); fetchReminders(); } catch {} };

  /* ── Render ── */
  if (!isBooted) return <BootScreen onComplete={() => setIsBooted(true)} />;

  return (
    <div className="app-container">
      <ParticleBackground voiceState={voiceState} />
      <audio ref={audioRef} style={{ display: 'none' }} />

      {/* ── Header ── */}
      <header className="hud-header">
        <h1 className="hud-title">
          MITRA <span className="neon-text">V1.0</span>
        </h1>
        <div className="header-controls">
          <div className={`voice-badge voice-badge-${voiceState}`}>
            <span className="voice-badge-dot" />
            {VOICE_STATE_CONFIG[voiceState]?.label || 'VOICE READY'}
          </div>
          <div className="connection-status">
            <span className="status-dot" /> SYS ACTIVE
          </div>
          <button
            onClick={() => { setVoiceOutput(v => !v); SoundFX.playClick(); }}
            className="neon-border-btn"
            style={{ width: 40, height: 38, padding: 0 }}
            title={voiceOutput ? 'Mute' : 'Unmute'}
          >
            {voiceOutput ? <Volume2 size={17} /> : <VolumeX size={17} />}
          </button>
        </div>
      </header>

      {/* ── Main Grid ── */}
      <main className="hud-grid">

        {/* Left sidebar */}
        <section className="hud-sidebar">
          {/* Telemetry */}
          <div className="hud-panel telemetry-widget">
            <h2 className="telemetry-header">SYSTEM CORE METRICS</h2>
            {[
              { label: 'CPU', val: `${systemStats.cpu_percent.toFixed(1)}%`, pct: systemStats.cpu_percent },
              { label: 'VRAM', val: `${systemStats.ram_percent.toFixed(1)}%`, pct: systemStats.ram_percent },
              { label: 'DISK', val: `${systemStats.disk_percent.toFixed(0)}%`, pct: systemStats.disk_percent },
            ].map(s => (
              <div key={s.label}>
                <div className="telemetry-row">
                  <span>{s.label}</span>
                  <span className="telemetry-value">{s.val}</span>
                </div>
                <div className="telemetry-bar-bg">
                  <div className="telemetry-bar-fill" style={{ width: `${s.pct}%` }} />
                </div>
              </div>
            ))}
            <div className="telemetry-row" style={{ marginTop: 14, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              <span>POWER</span>
              <span className="telemetry-value" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <Battery size={13} /> {systemStats.battery_percent}%{systemStats.battery_plugged ? ' ⚡' : ''}
              </span>
            </div>
          </div>

          {/* Command Module */}
          <div className="hud-panel" style={{ padding: 20, flex: 1 }}>
            <h2 className="telemetry-header" style={{ marginBottom: 8 }}>COMMAND MODULE</h2>
            <nav className="tab-nav">
              {['task','note','reminder'].map(t => (
                <button key={t} className={`tab-btn${activeForm === t ? ' active' : ''}`}
                  onClick={() => { setActiveForm(t); SoundFX.playClick(); }}>
                  {t === 'reminder' ? 'ALERT' : t.toUpperCase()}
                </button>
              ))}
            </nav>

            {activeForm === 'task' && (
              <form onSubmit={handleAddTask} className="action-form">
                <input className="hud-input" placeholder="Task title…" value={taskTitle} onChange={e => setTaskTitle(e.target.value)} required />
                <input className="hud-input" type="date" value={taskDue} onChange={e => setTaskDue(e.target.value)} />
                <button type="submit" className="neon-border-btn" style={{ width: '100%' }}><Plus size={14} /> ADD TASK</button>
              </form>
            )}
            {activeForm === 'note' && (
              <form onSubmit={handleAddNote} className="action-form">
                <input className="hud-input" placeholder="Note title…" value={noteTitle} onChange={e => setNoteTitle(e.target.value)} required />
                <textarea className="hud-input" placeholder="Content…" value={noteContent} onChange={e => setNoteContent(e.target.value)} style={{ height: 68, resize: 'none' }} />
                <button type="submit" className="neon-border-btn" style={{ width: '100%' }}><Plus size={14} /> SAVE NOTE</button>
              </form>
            )}
            {activeForm === 'reminder' && (
              <form onSubmit={handleAddReminder} className="action-form">
                <input className="hud-input" placeholder="Alert subject…" value={reminderTitle} onChange={e => setReminderTitle(e.target.value)} required />
                <input className="hud-input" type="datetime-local" value={reminderAt} onChange={e => setReminderAt(e.target.value)} required />
                <button type="submit" className="neon-border-btn" style={{ width: '100%' }}><Plus size={14} /> SET ALERT</button>
              </form>
            )}
          </div>
        </section>

        {/* Center column */}
        <section className="hud-center-column">
          <MitraOrb
            voiceState={voiceState}
            isRecording={isRecording}
            isTyping={isTyping}
            recordingStatus={recordingStatus}
            voiceStateText={voiceStateText}
          />

          {/* Chat terminal */}
          <div className="chat-terminal">
            <div className="chat-history">
              {messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)}
              {isTyping && !messages[messages.length - 1]?.isStreaming && (
                <div className="chat-bubble assistant">
                  <div className="bubble-header">
                    <span className="bubble-sender">MITRA CORE</span>
                  </div>
                  <div style={{ display: 'flex', gap: 2, height: 14, alignItems: 'center' }}>
                    <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            <div className="chat-input-bar">
              {attachedFile && (
                <div className="attachment-badge">
                  <span>📎 {attachedFile.filename}</span>
                  <button onClick={() => setAttachedFile(null)}><X size={13} /></button>
                </div>
              )}
              <form onSubmit={handleSendText} className="chat-form-row">
                <label className="neon-border-btn" style={{ width: 42, height: 42, padding: 0, borderRadius: 9, cursor: 'pointer' }}>
                  <input type="file" onChange={handleFileChange} style={{ display: 'none' }} disabled={uploading} />
                  <Paperclip size={17} />
                </label>
                <input
                  type="text" value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  placeholder='Message MITRA or say "Mitra"…'
                  className="chat-textarea"
                  style={{ height: 42 }}
                />
                <button type="button" onClick={isRecording ? stopRecording : startRecording}
                  className="neon-border-btn" style={{ width: 42, height: 42, padding: 0 }}>
                  {isRecording ? <MicOff size={17} style={{ color: 'var(--accent-color)' }} /> : <Mic size={17} />}
                </button>
                <button type="submit" className="neon-border-btn" style={{ width: 42, height: 42, padding: 0 }}>
                  <Send size={17} />
                </button>
              </form>
            </div>
          </div>
        </section>

        {/* Right sidebar */}
        <section className="hud-sidebar">
          {/* Tasks */}
          <div className="hud-panel registry-panel">
            <h2 className="telemetry-header" style={{ margin: '14px 14px 6px' }}>TASK QUEUE</h2>
            <div className="registry-list">
              {tasks.length === 0
                ? <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>No active tasks.</div>
                : tasks.map(t => (
                  <div key={t.id} className="registry-item">
                    <div className="registry-item-header">
                      <div className="checkbox-container" onClick={() => handleToggleTask(t)}
                        style={{ textDecoration: t.status === 'done' ? 'line-through' : 'none',
                                 color: t.status === 'done' ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                        <span className={`custom-checkbox${t.status === 'done' ? ' checked' : ''}`} />
                        <span className="registry-item-title">{t.title}</span>
                      </div>
                      <button onClick={() => handleDeleteTask(t.id)}
                        style={{ background: 'transparent', border: 'none', color: 'rgba(255,42,95,0.6)', cursor: 'pointer', display: 'flex' }}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    {t.due_date && (
                      <span className="registry-item-date" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Calendar size={11} /> {t.due_date}
                      </span>
                    )}
                  </div>
                ))}
            </div>
          </div>

          {/* Notes */}
          <div className="hud-panel registry-panel">
            <h2 className="telemetry-header" style={{ margin: '14px 14px 6px' }}>NOTEBOOK</h2>
            <div className="registry-list">
              {notes.length === 0
                ? <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>No notes.</div>
                : notes.map(n => (
                  <div key={n.id} className="registry-item">
                    <div className="registry-item-header">
                      <span className="registry-item-title" style={{ color: 'var(--primary-glow)' }}>{n.title}</span>
                      <button onClick={() => handleDeleteNote(n.id)}
                        style={{ background: 'transparent', border: 'none', color: 'rgba(255,42,95,0.6)', cursor: 'pointer', display: 'flex' }}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    {n.content && <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: 3, overflowWrap: 'anywhere' }}>{n.content}</p>}
                  </div>
                ))}
            </div>
          </div>

          {/* Reminders */}
          <div className="hud-panel registry-panel">
            <h2 className="telemetry-header" style={{ margin: '14px 14px 6px' }}>ALERTS</h2>
            <div className="registry-list">
              {reminders.length === 0
                ? <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>No alerts.</div>
                : reminders.map(r => (
                  <div key={r.id} className="registry-item">
                    <div className="registry-item-header">
                      <span className="registry-item-title" style={{ color: 'var(--accent-color)' }}>{r.title}</span>
                      <button onClick={() => handleDeleteReminder(r.id)}
                        style={{ background: 'transparent', border: 'none', color: 'rgba(255,42,95,0.6)', cursor: 'pointer', display: 'flex' }}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <span className="registry-item-date" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={11} /> {r.remind_at}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        </section>

      </main>
    </div>
  );
}
