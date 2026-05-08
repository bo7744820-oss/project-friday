import os
import json
import threading
import datetime
import subprocess
import webbrowser
import platform
from pathlib import Path

import openai
import requests
import speech_recognition as sr
from PyQt6.QtCore import QObject, pyqtSignal

from backend.system_monitor import collect_system_stats
from backend.utils import load_json, save_json, run_command
from voice.voice_engine import VoiceEngine

BASE_DIR = Path(__file__).resolve().parent.parent
MEMORY_DIR = BASE_DIR / "memory"
HISTORY_FILE = MEMORY_DIR / "chat_history.json"
CONFIG_FILE = MEMORY_DIR / "config.json"

DEFAULT_CONFIG = {
    "openai_api_key": os.environ.get("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY"),
    "weather_api_key": os.environ.get("WEATHER_API_KEY", "YOUR_WEATHER_API_KEY"),
    "news_api_key": os.environ.get("NEWS_API_KEY", "YOUR_NEWS_API_KEY"),
    "wake_word": "hey friday",
    "voice_rate": 175,
    "voice_volume": 0.9,
    "personality_mode": "default",
    "city": "New York",
    "tts_engine": "pyttsx3",
    "elevenlabs_api_key": "",
    "elevenlabs_voice_id": "21m00Tcm4TlvDq8ikWAM",
}

FRIDAY_SYSTEM_PROMPT = """You are FRIDAY, an advanced intelligent assistant modeled after a calm, efficient, slightly sarcastic AI.
Keep responses concise, emotionally aware, and helpful. Use plain conversational text only."""


class FridayCore(QObject):
    response_ready = pyqtSignal(str)
    speaking_started = pyqtSignal()
    speaking_finished = pyqtSignal()
    listening_started = pyqtSignal()
    listening_finished = pyqtSignal()
    system_stats_updated = pyqtSignal(dict)
    status_changed = pyqtSignal(str)
    wake_word_detected = pyqtSignal()
    error_occurred = pyqtSignal(str)
    startup_progress = pyqtSignal(int, str)

    def __init__(self):
        super().__init__()
        self.config = self._load_config()
        self.chat_history = self._load_history()
        self.is_listening = False
        self.is_speaking = False
        self.wake_word_active = True
        self.voice = VoiceEngine(self.config["voice_rate"], self.config["voice_volume"])
        self.recognizer = self._init_recognizer()
        self.microphone = self._init_microphone()
        self._init_openai_client()

        self.stats_timer = threading.Timer(2.0, self._emit_system_stats)
        self.stats_timer.daemon = True
        self.stats_timer.start()

    def _load_config(self):
        config = load_json(CONFIG_FILE, DEFAULT_CONFIG.copy())
        if config is None:
            config = DEFAULT_CONFIG.copy()
            save_json(CONFIG_FILE, config)
        for key, value in DEFAULT_CONFIG.items():
            config.setdefault(key, value)
        return config

    def _load_history(self):
        history = load_json(HISTORY_FILE, [])
        if history is None:
            history = []
        return history

    def _save_history(self):
        self.chat_history = self.chat_history[-100:]
        save_json(HISTORY_FILE, self.chat_history)

    def _init_recognizer(self):
        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 320
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.7
        return recognizer

    def _init_microphone(self):
        try:
            mic = sr.Microphone()
            with mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            return mic
        except Exception as err:
            self.error_occurred.emit(f"Microphone unavailable: {err}")
            return None

    def _init_openai_client(self):
        api_key = self.config.get("openai_api_key", "")
        if api_key and api_key != "YOUR_OPENAI_API_KEY":
            openai.api_key = api_key
            self.openai_enabled = True
        else:
            self.openai_enabled = False

    def startup_sequence(self):
        def sequence():
            steps = [
                (10, "Booting HUD overlay..."),
                (30, "Locking into secure channel..."),
                (55, "Loading conversational core..."),
                (75, "Warming vocal matrix..."),
                (90, "Initializing diagnostics..."),
                (100, "FRIDAY is online."),
            ]
            import time
            for percent, message in steps:
                self.startup_progress.emit(percent, message)
                time.sleep(0.35)
            greeting = self._get_greeting()
            self.response_ready.emit(greeting)
            self.speak(greeting)

        threading.Thread(target=sequence, daemon=True).start()

    def _get_greeting(self):
        hour = datetime.datetime.now().hour
        if hour < 12:
            suffix = "morning"
        elif hour < 18:
            suffix = "afternoon"
        else:
            suffix = "evening"
        return f"Good {suffix}. Systems are stable and the interface is ready. What's next?"

    def speak(self, text: str):
        def speak_thread():
            self.is_speaking = True
            self.speaking_started.emit()
            try:
                self.voice.speak(text)
            except Exception as err:
                self.error_occurred.emit(f"Speech error: {err}")
            finally:
                self.is_speaking = False
                self.speaking_finished.emit()

        threading.Thread(target=speak_thread, daemon=True).start()

    def listen_once(self):
        def listen_thread():
            if not self.microphone:
                self.error_occurred.emit("No microphone detected.")
                return
            self.is_listening = True
            self.listening_started.emit()
            self.status_changed.emit("LISTENING")
            try:
                with self.microphone as source:
                    audio = self.recognizer.listen(source, timeout=6, phrase_time_limit=12)
                transcript = self.recognizer.recognize_google(audio)
                self.process_command(transcript)
            except sr.WaitTimeoutError:
                self.error_occurred.emit("Listen timeout. Try again.")
            except sr.UnknownValueError:
                self.error_occurred.emit("I couldn't understand that.")
            except Exception as err:
                self.error_occurred.emit(f"Voice capture failed: {err}")
            finally:
                self.is_listening = False
                self.listening_finished.emit()
                self.status_changed.emit("READY")

        threading.Thread(target=listen_thread, daemon=True).start()

    def start_wake_word_detection(self):
        def wake_loop():
            while self.wake_word_active:
                if self.microphone and not self.is_listening and not self.is_speaking:
                    try:
                        with self.microphone as source:
                            audio = self.recognizer.listen(source, timeout=2, phrase_time_limit=4)
                        spoken = self.recognizer.recognize_google(audio).lower()
                        if self.config.get("wake_word", "hey friday") in spoken:
                            self.wake_word_detected.emit()
                            self.listen_once()
                    except (sr.WaitTimeoutError, sr.UnknownValueError, sr.RequestError):
                        pass
                    except Exception:
                        pass
                else:
                    import time
                    time.sleep(0.5)

        threading.Thread(target=wake_loop, daemon=True).start()

    def _emit_system_stats(self):
        stats = collect_system_stats()
        self.system_stats_updated.emit(stats)
        if self.wake_word_active:
            self.stats_timer = threading.Timer(2.0, self._emit_system_stats)
            self.stats_timer.daemon = True
            self.stats_timer.start()

    def process_command(self, text: str):
        clean_text = text.lower().strip()
        offline_response = self._handle_offline_commands(clean_text)
        if offline_response:
            self._append_history("user", text)
            self._append_history("assistant", offline_response)
            self._save_history()
            self.response_ready.emit(offline_response)
            self.speak(offline_response)
            return
        self._append_history("user", text)
        threading.Thread(target=self._ai_response, args=(text,), daemon=True).start()

    def _handle_offline_commands(self, text: str):
        now = datetime.datetime.now()
        if any(token in text for token in ["time", "current time", "what time"]):
            return f"It's {now.strftime('%I:%M %p')}."
        if any(token in text for token in ["date", "today", "day"]):
            return f"Today is {now.strftime('%A, %B %d, %Y')}."
        if text in ["hello", "hi", "hey friday", "hello friday", "hey"]:
            return "Hello. I'm online and listening."
        if "cpu" in text and any(token in text for token in ["usage", "how much", "percent"]):
            stat = collect_system_stats()
            return f"CPU is at {stat['cpu']:.1f}% and RAM usage is {stat['ram']:.1f}%."
        if "ram" in text or "memory" in text:
            stat = collect_system_stats()
            return f"Memory usage is {stat['ram']:.1f}% with {stat['ram_used']} GB used."
        if "battery" in text:
            stat = collect_system_stats()
            if stat['battery'] >= 0:
                state = "charging" if stat['plugged'] else "discharging"
                return f"Battery is {stat['battery']:.0f}% and {state}."
            return "Battery data is not available on this device."
        if "search" in text or "google" in text:
            query = text.replace("search", "").replace("google", "").replace("for", "").strip()
            if query:
                webbrowser.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
                return f"Searching Google for {query}."
        if "play" in text and "youtube" in text:
            query = text.replace("play", "").replace("on youtube", "").replace("youtube", "").strip()
            webbrowser.open(f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}")
            return f"Opening YouTube results for {query}."
        if "open" in text:
            app_response = self._handle_open_command(text)
            if app_response:
                return app_response
        if "volume" in text:
            return self._handle_volume_command(text)
        if "shutdown" in text or "shut down" in text:
            response = "Preparing shutdown sequence. Goodbye."
            self.response_ready.emit(response)
            self.speak(response)
            self._system_shutdown()
            return response
        if "restart" in text or "reboot" in text:
            response = "Rebooting now. Stay safe."
            self.response_ready.emit(response)
            self.speak(response)
            self._system_restart()
            return response
        if text.startswith("run ") or text.startswith("execute "):
            command = text.replace("run ", "").replace("execute ", "").strip()
            return self._run_terminal(command)
        return None

    def _handle_open_command(self, text: str):
        apps = {
            "chrome": ["chrome", "google-chrome", "msedge"],
            "firefox": ["firefox"],
            "notepad": ["notepad"],
            "calculator": ["calc"],
            "vscode": ["code"],
            "spotify": ["spotify"],
            "terminal": ["cmd", "powershell"],
        }
        for app_name, commands in apps.items():
            if app_name in text:
                for cmd in commands:
                    try:
                        subprocess.Popen(cmd.split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        return f"Opening {app_name}."
                    except Exception:
                        continue
                return f"I couldn't locate {app_name} on this machine."
        return None

    def _handle_volume_command(self, text: str):
        try:
            if "up" in text or "increase" in text:
                if platform.system() == "Windows":
                    run_command("nircmd changesysvolume 5000")
                return "Volume increased."
            if "down" in text or "decrease" in text or "lower" in text:
                if platform.system() == "Windows":
                    run_command("nircmd changesysvolume -5000")
                return "Volume decreased."
            if "mute" in text:
                if platform.system() == "Windows":
                    run_command("nircmd mutesysvolume 2")
                return "Audio muted."
        except Exception as err:
            return f"Unable to adjust volume: {err}"
        return "Specify volume up, down, or mute."

    def _run_terminal(self, command: str):
        try:
            output = run_command(command)
            return f"Command executed: {output[:190]}"
        except Exception as err:
            return f"Terminal execution failed: {err}"

    def _system_shutdown(self):
        if platform.system() == "Windows":
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
        elif platform.system() == "Linux":
            subprocess.Popen(["shutdown", "-h", "now"])

    def _system_restart(self):
        if platform.system() == "Windows":
            subprocess.Popen(["shutdown", "/r", "/t", "0"])
        elif platform.system() == "Linux":
            subprocess.Popen(["reboot"])

    def _ai_response(self, prompt: str):
        if not self.openai_enabled:
            response = self._offline_fallback(prompt)
            self.response_ready.emit(response)
            self.speak(response)
            self._append_history("assistant", response)
            self._save_history()
            self.status_changed.emit("READY")
            return

        try:
            messages = [{"role": "system", "content": FRIDAY_SYSTEM_PROMPT}]
            for item in self.chat_history[-12:]:
                messages.append({"role": item["role"], "content": item["content"]})
            messages.append({"role": "user", "content": prompt})
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=220,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self._append_history("assistant", reply)
            self._save_history()
            self.response_ready.emit(reply)
            self.speak(reply)
            self.status_changed.emit("READY")
        except openai.error.AuthenticationError:
            self.error_occurred.emit("OpenAI key invalid. Update config.")
            self.openai_enabled = False
        except Exception as err:
            fallback = self._offline_fallback(prompt)
            self.response_ready.emit(fallback)
            self.speak(fallback)
            self.status_changed.emit("READY")

    def _offline_fallback(self, text: str) -> str:
        patterns = [
            "My network link is down, but I'm still operational.",
            "I'm in offline mode. I can handle commands, but not deep conversation.",
            f"I heard '{text}', but the cloud is unavailable right now.",
        ]
        return patterns[0]

    def _append_history(self, role: str, content: str):
        self.chat_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.datetime.now().isoformat(),
        })

    def get_weather(self, city: str = None) -> dict:
        city = city or self.config.get("city", "New York")
        api_key = self.config.get("weather_api_key", "")
        if not api_key or api_key == "YOUR_WEATHER_API_KEY":
            return {"error": "Weather API key is not configured."}
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            data = requests.get(url, timeout=6).json()
            return {
                "city": data["name"],
                "temp": data["main"]["temp"],
                "description": data["weather"][0]["description"].capitalize(),
                "humidity": data["main"]["humidity"],
            }
        except Exception as err:
            return {"error": str(err)}

    def get_news(self) -> list:
        api_key = self.config.get("news_api_key", "")
        if not api_key or api_key == "YOUR_NEWS_API_KEY":
            return []
        try:
            url = f"https://newsapi.org/v2/top-headlines?language=en&pageSize=5&apiKey={api_key}"
            response = requests.get(url, timeout=6).json()
            return [
                {"title": article["title"], "source": article["source"]["name"]}
                for article in response.get("articles", [])[:5]
            ]
        except Exception:
            return []

    def clear_history(self):
        self.chat_history = []
        self._save_history()
