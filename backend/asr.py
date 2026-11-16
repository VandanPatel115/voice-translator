import os
import sys
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

ASR_MODEL = "whisper-large-v3-turbo"

def transcribe(wav_bytes: bytes, prompt: str = "") -> str:
    """Send WAV audio to Whisper and return the English transcript."""
    result = client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=ASR_MODEL,
        language="en",
        prompt=prompt,
        temperature=0,
    )
    return result.text.strip()

if __name__ == "__main__":
    path = sys.argv[1]
    with open(path, "rb") as f:
        audio = f.read()

    start = time.perf_counter()
    text = transcribe(audio)
    ms = (time.perf_counter() - start) * 1000

    print(f"Transcript: {text}")
    print(f"ASR time: {ms:.0f} ms")

    hinted = transcribe(audio, prompt="Google Meet, Asterisk, Zoom, Slack, ETA.")
    print(f"With prompt: {hinted}")