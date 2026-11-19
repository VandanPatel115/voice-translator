import os
import sys
import time

from dotenv import load_dotenv
from groq import Groq
from backend.preprocess import clean_fillers
from backend.preprocess import clean_fillers, protect, restore
from backend.preprocess import clean_fillers, expand_abbreviations, protect, restore

load_dotenv()
client = Groq(api_key=os.environ["GROQ_API_KEY"])

MT_MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are a real-time interpreter. Translate spoken English into natural,
spoken Hindi in Devanagari script, the way an educated Indian speaker would actually say
it in conversation, not formal written Hindi.

The input comes from speech recognition, so:
- It may contain recognition errors. If a word is clearly wrong from context, translate
  what the speaker obviously meant. Never add information that was not said.
- It may contain conversational fillers ("you know", "I mean", "like", "basically").
  Drop them unless they carry real meaning.

Rules:
1. Tokens like ⟦0⟧ and ⟦1⟧ are protected names. Copy each one exactly.
2. Keep English words that Indians commonly use in Hindi conversation, such as
   meeting, call, report, file, email, lunch.
3. Times: "5pm" → "शाम 5 बजे", "9.30am" → "सुबह 9:30 बजे", "2pm" → "दोपहर 2 बजे".
4. A day like "tomorrow" says WHEN something happens. Put it next to the time
   ("कल शाम 5 बजे"), not in front of the noun ("कल की मीटिंग" is wrong unless the
   meeting itself is tomorrow).
5. "Move", "shift" or "reschedule" a meeting → "शिफ्ट करना" or "रखना", never "ले जाना".
6. Tone: casual English (hey, dude, bro, wanna) → तुम and यार. Polite or neutral → आप.
7. Return ONLY the Hindi translation."""

EXAMPLES = [
    ("Basically, I mean, the build failed again.",
     "बिल्ड फिर से फेल हो गया।"),
    ("Can we shift the call to 3pm on Monday?",
     "क्या हम कॉल को सोमवार दोपहर 3 बजे शिफ्ट कर सकते हैं?"),
    ("Can you here me clearly?",
     "क्या आप मुझे साफ़ सुन पा रहे हैं?"),
    ("Yo bro, you coming to the party tonight?",
     "अरे यार, तुम आज रात पार्टी में आ रहे हो?"),
]

def _ask_llm(text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for en, hi in EXAMPLES:
        messages.append({"role": "user", "content": en})
        messages.append({"role": "assistant", "content": hi})
    messages.append({"role": "user", "content": text})

    resp = client.chat.completions.create(
        model=MT_MODEL,
        temperature=0.2,
        reasoning_effort="low",
        messages=messages,
    )
    return resp.choices[0].message.content.strip()


def translate(english: str) -> str:
    """Translate English text into Hindi, keeping glossary names in English."""
    english = clean_fillers(english)
    if not english:
        return ""
    english = expand_abbreviations(english)

    protected, mapping = protect(english)
    for _ in range(2):
        hindi = restore(_ask_llm(protected), mapping)
        if hindi is not None:
            return hindi

    return _ask_llm(english)   # fallback: translate without protection

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
