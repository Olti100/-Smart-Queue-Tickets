from __future__ import annotations

import threading

import pyttsx3


class VoiceNotifier:
    def __init__(self):
        self.engine = pyttsx3.init()
        self._lock = threading.Lock()

    def announce(self, message: str) -> None:
        def _speak():
            with self._lock:
                self.engine.say(message)
                self.engine.runAndWait()

        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()


voice_notifier = VoiceNotifier()
