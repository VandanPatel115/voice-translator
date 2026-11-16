import os
import sys
import time

from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

MT_MODEL = "openai/gpt-oss-120b"

SYSTEMP_PROMPT = """You translate spoken English into natural spoken Hindi, written in Devaanagari. Return ONLY the Hindi translation, with no explanation"""

def translate(english: str) -> str:
    """Translate English text into Hindi"""
    resp = client.chat.completions.create(
        model=MT_MODEL,
        temperature=0.2,
        reasoning_effort="low",
        messages=[
            {"role": "system", "content": SYSTEMP_PROMPT},
            {"role": "user", "content": english},
        ],
    )
    return resp.choices[0].message.content.strip()

if __name__ == "__main__":
    tests = [
        "Hey Howie, what's up. how are you doing?",
        "Please join the Google Meet. I'll share the Asterisk server details there.",
        "So, you know, I think we should finish the report today.",
        "Can we move the meeting to 5pm tomorrow?",
        "What's the ETA? The delivery was due at 9.30am on 12th November.",
        "Hey dude, wanna grab lunch after this?",
    ]
    for text in tests:
        start = time.perf_counter()
        hindi = translate(text)
        ms = (time.perf_counter() - start) * 1000
        print(f"{ms:5.0f} ms | {text}\n -> {hindi}\n")
