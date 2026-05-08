# FRIDAY AI Assistant

This project is a futuristic desktop AI assistant inspired by Marvel's FRIDAY.

## Overview

- Modern glassmorphism PyQt6 GUI
- Voice input and speech output
- Wake word detection: "Hey Friday"
- OpenAI conversational intelligence
- Real-time system monitoring dashboard
- Local memory and chat history
- Weather and news integration
- Terminal command execution and app launching

## Architecture

- `main.py` — application entry point
- `frontend/` — PyQt6 UI and animation
- `backend/` — assistant logic, system monitoring, utilities
- `assets/` — styles and visual assets
- `voice/` — voice engine helper package
- `memory/` — persisted chat and configuration files
- `modules/` — plugin extension framework

## Requirements

- Python 3.11+
- PyQt6
- psutil
- speechrecognition
- pyttsx3
- openai
- requests
- pyaudio or sounddevice (for microphone support)

## Setup Instructions

1. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Configure environment variables or `memory/config.json`:
   - `OPENAI_API_KEY`
   - `WEATHER_API_KEY`
   - `NEWS_API_KEY`
   - `ELEVENLABS_API_KEY` (optional)
4. Run the assistant:
   ```powershell
   python main.py
   ```

## Notes

- The GUI is designed for dark mode with neon blue accents.
- Wake word detection runs in the background and can trigger listening.
- The assistant falls back to offline responses when OpenAI is unavailable.
- Use `memory/chat_history.json` to preserve context across sessions.
