import pyttsx3


class VoiceEngine:
    def __init__(self, rate: int = 175, volume: float = 0.88):
        self.engine = None
        self.rate = rate
        self.volume = volume
        self._initialize_engine()

    def _initialize_engine(self):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)
            voices = self.engine.getProperty("voices")
            for voice in voices:
                name = getattr(voice, "name", "").lower()
                if any(keyword in name for keyword in ["female", "zira", "samantha", "victoria", "karen"]):
                    self.engine.setProperty("voice", voice.id)
                    break
        except Exception:
            self.engine = None

    def speak(self, text: str):
        if not self.engine:
            return
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception:
            pass
