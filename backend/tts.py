import base64
import os
import sys
import time

from dotenv import load_dotenv
from sarvamai import SarvamAI

load_dotenv()
client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

TTS_MODEL = "bulbul:v3"
TTS_SPEAKER = "shubh"

def synthesize(hindi: str) -> bytes:
    """Convert Hindi text into WAV audio bytes."""
    resp = client.text_to_speech.convert(
        text=hindi,
        language_code="hi-IN",
        model=TTS_MODEL,
        speaker=TTS_SPEAKER,
        output_audio_codec="wav",
    )
    return base64.b64decode(resp.audios[0])

if __name__ == "__main__":
    text = sys.argv[1] if len(sys.argv) > 1 else "क्या हम मीटिंग को कल शाम 5 बजे कर सकते हैं?"
    start = time.perf_counter()
    audio = synthesize(text)
    ms = (time.perf_counter() - start) * 1000

    os.makedirs("out", exist_ok=True)
    with open("out/test_hi.wav", "wb") as f:
        f.write(audio)
    print(f"TTS time: {ms:.0f} ms, {len(audio)} bytes -> out/test_hi.wav")
