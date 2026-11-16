import os
import sys
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

ASR_MODEL = "whisper-large-v3-turbo"
ASR_PROMPT = "We joined the Google Meet call and discussed the Asterisk server, Zoom and Slack."

def transcribe(wav_bytes: bytes, prompt: str = ASR_PROMPT, model: str = ASR_MODEL) -> str:
    """Send WAV audio to Whisper and return the English transcript."""
    result = client.audio.transcriptions.create(
        file=("audio.wav", wav_bytes),
        model=model,
        language="en",
        prompt=prompt,
        temperature=0,
    )
    return result.text.strip()


def timed(audio: bytes, **kwargs) -> tuple[str, float]:
    """Run transcribe and return (text, milliseconds)."""
    start = time.perf_counter()
    text = transcribe(audio, **kwargs)
    return text, (time.perf_counter() - start) * 1000


if __name__ == "__main__":
    with open(sys.argv[1], "rb") as f:
        audio = f.read()

    hint = "Google Meet, Asterisk, Zoom, Slack, ETA."

    for label, kwargs in [
        ("Turbo", {}),
        ("Turbo + prompt", {"prompt": hint}),
        ("Large", {"model": "whisper-large-v3"}),
        ("Large + prompt", {"model": "whisper-large-v3", "prompt": hint}),
    ]:
        text, ms = timed(audio, **kwargs)
        print(f"{label:<16} {ms:5.0f} ms | {text}")