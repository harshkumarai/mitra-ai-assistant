# MITRA Web Application - Complete Setup Guide

## Overview

Your **MITRA AI assistant** project has a complete web application structure with:
- **FastAPI Backend** with REST API, WebSocket support, and Gemini AI integration
- **React/Vite Frontend** with modern UI, voice input, and real-time features
- **Database integration** for conversation history, tasks, notes, and reminders
- **Voice features** with Web Speech API for microphone input and browser speech synthesis

## Current Status

✅ **Backend**: Fully functional FastAPI server running on port 8001  
✅ **Frontend**: React application built and ready (dist folder exists)  
✅ **API Integration**: All endpoints working (chat, speech, files, notes, reminders, tasks, system)  
✅ **Database**: SQLite database initialized and operational  
✅ **Environment**: .env file loading correctly with API keys detected  
✅ **Dependencies**: All required Python packages installed  

## Quick Start

### Option 1: Using the Automated Run Script (Recommended)

```bash
cd /Users/harshkumar/Desktop/AI_ASSISTANT/jarvis
python3 run.py
```

This script will:
1. Check for existing processes on port 8001 and terminate them
2. Start the FastAPI backend server
3. Wait for server initialization
4. Automatically open Google Chrome with the MITRA dashboard
5. Display server status and URLs

### Option 2: Manual Start

```bash
cd /Users/harshkumar/Desktop/AI_ASSISTANT/jarvis
python3 main.py
```

Then manually open: `http://localhost:8001`

## Access Points

Once the server is running, access:

- **📱 Main Dashboard**: http://localhost:8001
- **🔧 API Documentation**: http://localhost:8001/docs (Swagger UI)
- **💚 Health Check**: http://localhost:8001/health
- **🌐 WebSocket**: ws://localhost:8001/ws/chat

## Wake Words

MITRA responds to the following wake words:
- **"Mitra"** — primary wake word
- **"Hey Mitra"** — alternative activation phrase
- **"Jarvis"** — legacy backward-compatible wake word

## Project Structure

```
jarvis/
├── main.py                 # FastAPI application entry point
├── run.py                  # Automated launcher script
├── voice_assistant.py      # Standalone voice assistant loop
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables with API keys
├── backend/
│   ├── api/               # REST API endpoints
│   │   ├── chat.py        # Chat/AI endpoints
│   │   ├── speech.py      # Voice input/output
│   │   ├── files.py       # File handling
│   │   ├── notes.py       # Notes management
│   │   ├── reminders.py   # Reminders system
│   │   ├── tasks.py       # Task management
│   │   └── system.py      # System telemetry
│   ├── ai/               # AI integration
│   │   ├── chat_engine.py # Gemini chat engine
│   │   ├── client.py     # Gemini API client
│   │   └── prompts.py    # MITRA AI personality & prompts
│   ├── commands/         # Command dispatcher
│   ├── database/         # SQLite database
│   ├── memory/           # Conversation memory
│   ├── speech/           # Speech processing (STT/TTS/wake word)
│   ├── utils/            # Utilities
│   └── config.py         # Configuration management
└── frontend/
    ├── src/              # React source code
    │   ├── App.jsx       # Main React component
    │   ├── App.css       # Styling
    │   └── main.jsx      # React entry point
    ├── dist/             # Built frontend (ready to serve)
    └── package.json      # Node dependencies
```

## Features

### 🤖 AI Chat
- Real-time conversation with Gemini AI
- MITRA personality: professional, friendly, concise
- Conversation history persistence
- Session management
- Context-aware responses

### 🎤 Voice Input
- Web Speech API for microphone input
- Real-time speech-to-text
- Voice command recognition

### 🔊 Voice Output
- Browser speech synthesis for TTS
- Multiple voice options
- Volume and rate control

### 📝 Productivity Tools
- **Tasks**: Create, manage, and track tasks
- **Notes**: Create and organize notes
- **Reminders**: Set and manage reminders
- **Files**: Upload and process files (PDF, DOCX)

### 💾 Database
- SQLite database for persistence
- Conversation history
- User data storage
- Automatic initialization

### 📊 System Monitoring
- CPU usage monitoring
- RAM usage tracking
- Battery status
- Network statistics
- Disk usage

## Environment Configuration

The `.env` file is located at `jarvis/.env` and contains:

```env
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
ELEVENLABS_VOICE_ID=auq43ws1oslv0tO4BDa7
LOG_LEVEL=INFO
MICROPHONE_INDEX=2
TTS_RATE=175
TTS_VOLUME=1.0
WAKE_WORD_ENABLED=true
WAKE_WORD=mitra
```

### API Keys Setup

1. **Gemini API Key** (Required for AI features):
   - Get from: https://makersuite.google.com/app/apikey
   - Add to `.env`: `GEMINI_API_KEY=your_key_here`

2. **ElevenLabs API Key** (Optional for premium TTS):
   - Get from: https://elevenlabs.io/app/settings/api-keys
   - Add to `.env`: `ELEVENLABS_API_KEY=your_key_here`

## Troubleshooting

### Port Already in Use
```bash
lsof -ti:8001 | xargs kill -9
```

### Frontend Not Loading
1. Check if the `dist/` folder exists in `jarvis/frontend/`
2. Rebuild: `cd jarvis/frontend && npm run build`

### Database Issues
```bash
cd /Users/harshkumar/Desktop/AI_ASSISTANT/jarvis
rm jarvis.db
python3 main.py  # Restart to recreate
```

### Microphone Not Working
- Check browser permissions for microphone access
- Ensure you're on HTTPS or localhost
- Try Chrome (recommended)

## Summary

MITRA is a **fully functional web-based AI assistant** with:
- ✅ Complete FastAPI backend with all features
- ✅ Modern React frontend with voice capabilities
- ✅ Gemini AI integration with MITRA personality
- ✅ Wake words: "Mitra", "Hey Mitra" (+ legacy "Jarvis")
- ✅ Database persistence
- ✅ Voice input/output
- ✅ Productivity tools (tasks, notes, reminders)
- ✅ System monitoring
- ✅ WebSocket support

Run `python3 run.py` in the `jarvis` directory to launch MITRA.
