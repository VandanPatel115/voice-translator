# Findings log

Observations from building the English → Hindi voice translation pipeline.
Each entry records what I tested, what happened, and what I decided.

---

## Phase 1 — Offline pipeline (file in, Hindi audio out)

### Stack used
- ASR: Groq Whisper (`whisper-large-v3-turbo`)
- Translation: Groq `openai/gpt-oss-120b`, `reasoning_effort="low"`, temperature 0.2
- TTS: Sarvam `bulbul:v3`, speaker `shubh`, WAV output

### 1. ASR model choice: turbo vs large

Tested both Whisper models, with and without a context prompt.

| Setting | fast.wav | entities.wav |
| --- | --- | --- |
| Turbo | "Hey Howie, what's up…" | "…the asterisk server…" |
| Turbo + prompt | "Hey Javi, what's up…" | "…the Asterisk server…" |
| Large | "Hey, Howie, what's up?…" | "…the Asterisk server…" |
| Large + prompt | "Hey, Howie, what's up?…" | "…the Asterisk server…" |

- Large was roughly 100 ms slower than turbo.
- Large did not fix the fast-speech error ("Howie").
- The prompt fixed "Asterisk" capitalisation on turbo.

**Decision:** turbo + context prompt. The larger model adds latency without fixing
the error that actually occurred.

### 2. Fast speech: "how are you" → "Howie"
- Said: "Hey how are you, what's up, how are you doing?"
- Whisper: "Hey Howie, what's up, how are you doing?"
- Spoken quickly, "how are you" ran together and was matched to a name.
  The second, clearer "how are you" was transcribed correctly.
- Both Whisper models made the same mistake.
- The error passed straight through translation: "हे हाउई…"
- **Plan:** tell the LLM its input is ASR output that may contain errors, and let it
  repair obvious ones from context (Phase 4).

### 3. Named entity: "Asterisk"
- Turbo wrote "asterisk" (lowercase) — treated as the `*` symbol, not the
  telephony software.
- A context prompt with glossary terms fixed it.
- In translation, the LLM transliterated names (गूगल मीट, एस्टरिस्क) rather than
  translating them, but there is no guarantee it always will.
- **Plan:** glossary + placeholder tokens, restored in code (Phase 4).

### 4. Side effect: the prompt can make things worse
- With a prompt listing names, turbo turned "Howie" into "Javi" on fast.wav.
- A list of proper nouns primes Whisper to expect names.
- **Change made:** prompt rewritten as a natural sentence instead of a bare list.
  Effect still to be measured.

### 5. Fillers
- Whisper removed hesitation sounds ("uh", "um") by itself.
- It kept discourse fillers: "So, you know, …"
- The LLM's handling of "you know" was **inconsistent across runs**:
  - Run 1: dropped → "तो, मुझे लगता है कि…"
  - Run 2: translated literally → "तो, आप जानते हैं, …"
- **Lesson:** one passing run proves nothing; test each case multiple times.
- **Plan:** explicit filler rule + few-shot examples in the prompt; keep a regex
  for hesitation sounds as a safety net for other ASR models.

### 6. Times and abbreviations
- Whisper output format varies: "5pm", "9.30am" (dot, not colon).
- Translation: "5pm" → "शाम 5 बजे" ✅, "9.30am" → "सुबह 9:30 बजे",
  "ETA" → "अनुमानित समय" ✅
- The LLM merged and reordered the two sentences in numbers.wav.
- TODO: note how TTS pronounced "9:30".

### 7. Meaning shift: "tomorrow"
- English: "Can we move the meeting to 5pm tomorrow?"
- Output: "क्या हम **कल की मीटिंग** को शाम 5 बजे…" = "tomorrow's meeting"
- The English means the meeting is being moved *to* tomorrow; the Hindi says the
  meeting *is* tomorrow. Happened in both runs, so it is consistent, not random.
- "move" was also translated literally as "ले जा सकते हैं" (carry) in one run.
- Fluent-sounding output can still change the meaning — needs human review in
  evaluation, not just automatic scores.

### 8. TTS observations
- Same sentence synthesised twice gave different file sizes (150,572 vs 135,520
  bytes) — TTS output is not deterministic.
- "Google Meet" in Latin vs Devanagari script produced files of identical size
  (60,256 bytes). TODO: confirm with `cmp` whether the audio is identical.
- TODO: note how natural the voice sounds.

### 9. Latency baseline (single run, sequential, non-streaming)

| File | ASR | MT | TTS | Total |
| --- | --- | --- | --- | --- |
| casual | 423 ms | 373 ms | 740 ms | 1535 ms |
| entities | 270 ms | 788 ms | 1104 ms | 2162 ms |
| fast | 273 ms | 278 ms | 599 ms | 1149 ms |
| fillers | 291 ms | 495 ms | 909 ms | 1694 ms |
| meeting | 255 ms | 277 ms | 648 ms | 1180 ms |
| numbers | 277 ms | 582 ms | 1482 ms | 2341 ms |

- TTS is the slowest stage in every case and grows with sentence length.
- The first ASR call was slower (423 ms vs ~270 ms) — connection cold start.
- These are single runs; Phase 6 will report medians over 20+ utterances.
- **Plan:** streaming TTS (Phase 5) so playback starts on the first audio chunk.