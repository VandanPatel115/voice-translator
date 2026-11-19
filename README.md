# English → Hindi Live Voice Translator

Speak English into your microphone and hear it back in Hindi a couple of seconds later.

**Live working link:** (https://voice-translator-rust.vercel.app/)

I built this as a take-home assignment for the Full Stack Developer role at Gnani.ai. The brief asked for a real-time voice-to-voice pipeline: take live audio, transcribe it to English, translate it to Hindi, and speak the Hindi back, while dealing with a list of messy real-world problems like accents, filler words, brand names, and people talking over the output.

This README covers what I built, why I made the choices I did, and what I measured along the way. That includes the parts that still don't work perfectly.

> **A note on the brief:** it lists "Grok" as an option for speech recognition. I've assumed this meant **Groq**, which hosts OpenAI's Whisper models. Grok is xAI's chatbot and doesn't do speech recognition, so Groq's Whisper is what I used.

---

## How it works

```
 Browser                                    Server (Python, FastAPI)
┌──────────────────┐   PCM frames      ┌───────────────────────────────────────────┐
│ Mic capture      │ ───────────────▶  │ Segment ──▶ ASR ──▶ Translate ──▶ TTS     │
│ (AudioWorklet)   │   over WebSocket  │ Silero    Groq      rules +       Sarvam  │
│                  │                   │ VAD       Whisper   LLM           Bulbul  │
│ Playback queue   │ ◀───────────────  │                                           │
└──────────────────┘   audio chunks    └───────────────────────────────────────────┘
```

1. **The browser captures the mic** with an AudioWorklet, converts the audio to 16 kHz, 16-bit PCM (the format speech models expect) and streams it to the server in 32 ms frames over a WebSocket.
2. **The server listens for pauses.** Silero VAD scores every frame for "is someone speaking?", and a small state machine cuts the stream into sentences whenever you pause for 600 ms.
3. **Groq Whisper transcribes** each sentence to English.
4. **The text is cleaned up in code, then translated.** Filler sounds are removed, abbreviations expanded and brand names protected, and then an LLM (`openai/gpt-oss-120b` on Groq) translates to Hindi.
5. **Sarvam's Bulbul model streams the Hindi audio back** in chunks, and the browser stitches them together and plays them as they arrive.

On the server, receiving audio and running the models happen in two separate tasks connected by a queue. The receiving loop gets a new frame every 32 ms and never waits for a model, so audio doesn't pile up while a sentence is being translated.

### Why Hindi needs whole sentences

Hindi usually puts the verb at the end. "Can we **move** the meeting to 5 PM tomorrow?" becomes "क्या हम मीटिंग को कल शाम 5 बजे **कर सकते हैं**?". You can't translate the start of the sentence properly until you've heard the end, so the system waits for a natural pause instead of translating word by word. That pause is the single biggest chunk of the latency, and it's a deliberate trade-off.

---

## Tech stack

| Part | What I used | Why |
| --- | --- | --- |
| Speech recognition | Groq `whisper-large-v3-turbo` | Fast and cheap. I compared it against `whisper-large-v3` (details below) and turbo won. |
| Translation | Groq `openai/gpt-oss-120b`, `reasoning_effort="low"` | An LLM can follow rules a plain translation API can't, such as "keep brand names in English" or "drop fillers". Low reasoning effort keeps it fast. |
| Hindi speech | Sarvam `bulbul:v3`, streaming over WebSocket | Built for Indian languages, and its streaming API sends the first audio in about a quarter of a second. |
| Voice activity detection | Silero VAD, run with ONNX Runtime | Small, accurate, runs on CPU in about a millisecond per frame. I started with the PyTorch version and switched to ONNX for deployment (see below). |
| Backend | Python, FastAPI, Uvicorn, `asyncio` | Native WebSocket support, and async lets the stages overlap. |
| Frontend | Plain HTML and JavaScript, Web Audio API | Audio capture and playback are easier to reason about without a framework in the way. |
| Hosting | Vercel (Python Functions with WebSockets) | Free, HTTPS out of the box (browsers require it for microphone access), and it redeploys on every push. |

---

## Deploying to Vercel

Getting this onto Vercel took more than pushing the code, and the changes made the app better anyway:

- **Dropping PyTorch.** The PyTorch version of Silero VAD pulls in PyTorch itself, which is far bigger than Vercel's 500 MB limit for Python functions. The same Silero model ships as a small ONNX file, so I run it with ONNX Runtime instead and removed PyTorch entirely. Before removing it, I checked the ONNX version gave the same speech probabilities as the PyTorch one on the same recording, frame by frame.
- **One detail the PyTorch wrapper hid.** The PyTorch version quietly glues the last 64 samples of each frame onto the front of the next one, so the model always sees a little context. Calling the ONNX model directly, I had to do that myself, so each input is 576 samples, not 512.
- **Each session gets its own VAD memory.** Silero remembers recent audio between frames. Originally that memory was shared by the whole server, which was fine on my laptop but would have let two people on a public URL corrupt each other's speech detection. The model is still loaded once and shared, but each connection now keeps its own state.
- **Secure WebSockets.** The page connects with `wss://` when it's served over HTTPS and `ws://` locally. Browsers block an unencrypted connection from a secure page.

---

## The edge cases from the brief

| Edge case | What I did | How it turned out |
| --- | --- | --- |
| **Strong accents or fast speech** | Forced Whisper to English, gave it a context prompt, compared two Whisper models, and told the LLM its input is speech-recognition output that may contain mistakes. | Said quickly, "Hey, how are you" came out as "Hey **Howie**" from *both* Whisper models. The translation step now repairs this in 4 out of 5 runs, without touching real names (I added tests with "Rahul" and "Howard" to make sure it doesn't). |
| **Brand names mistranslated** | Glossary names are swapped for placeholder tokens like `⟦0⟧` before translation and put back afterwards in code. If a token goes missing, the translation is retried, and if it fails again, it's translated without protection. | "Google Meet" and "Asterisk" went from 0/3 to 5/5. Asking the LLM nicely never got there; enforcing it in code did. |
| **Partial inputs** | Only complete sentences are translated, cut at a 600 ms pause. | I measured the pauses inside a sentence full of "uh"s and "um"s: none lasted more than about 64 ms, so 600 ms never splits a sentence on a hesitation. Shorter thresholds respond faster but break sentences apart. |
| **Fillers** | A regex removes hesitation sounds before translation; the LLM is told to drop "you know", "I mean" and similar. | Whisper already drops most "uh"s, so the regex is a safety net. It uses word boundaries so "umbrella" and "hummus" survive. "You know" went from translated literally in some runs to dropped every time. |
| **Latency buildup** | Streaming TTS, a warm Sarvam connection opened when the session starts, and the queue-based design. | Time to first Hindi audio after translation dropped from about 940 ms to about 270 ms. See the latency section. |
| **Formal vs casual tone** | Prompt rules plus examples: casual English gets तुम and यार, polite or neutral English gets आप. | 5/5 on both the formal and casual test sentences. Tone isn't remembered across sentences yet. |
| **Numbers, dates and abbreviations** | Prompt rules for times ("5pm" → "शाम 5 बजे"); abbreviations like ETA and ASAP expanded to full words in code before translation. | Whisper writes times inconsistently ("5pm", "5 pm", "9.30am"), so the rules had to cover every variant. |
| **User talks over the Hindi audio** | When the server detects new speech while audio is playing, the browser stops playback and ignores the rest of that sentence's audio. | Works well with headphones. With laptop speakers the mic can hear the Hindi audio, which can trigger a false interruption. |

---

## Measuring translation quality

The first thing I noticed while testing was that the same English sentence didn't always produce the same Hindi. "You know" was dropped in one run and translated literally as "आप जानते हैं" in the next. Trying a prompt change once and judging it by eye wasn't going to work.

So I wrote a small evaluation script (`tests/eval_translate.py`). It runs 12 test sentences several times each, checks every output against simple rules, and prints a pass rate. Every change to the translation step got measured against it:

| Step | Change | Pass rate |
| --- | --- | --- |
| Baseline | Minimal prompt | 50% |
| + Regex | Hesitation sounds removed in code | 60% |
| + Placeholders | Brand names protected in code | 73% |
| + Prompt rules and examples | Fillers, times, tone, "move the meeting", speech-recognition errors | 90% |
| + Abbreviation expansion | ETA, ASAP etc. expanded in code | 98% |

The final run scored 54/60. The 5 "Howard" failures were the test's fault, not the translation's: the model kept the name in Latin script, and my check only looked for the Devanagari spelling. Counting those as passes, it's 59/60.

Two lessons from this:

- **Code fixed the mechanical problems completely; the prompt fixed the judgement calls.** Fillers, names and abbreviations didn't need an LLM's opinion, so they're handled with plain code that works every time.
- **Tests can be wrong too.** Three separate times a failure turned out to be a bug in my check rather than in the translation. When a test fails, I now check the test first.

The few-shot examples in the prompt are deliberately different sentences from the test cases. If the examples were the test sentences, the scores would only prove the model can copy, not that it generalises.

These are simple string checks, so they're a signal rather than a perfect judge. A natural translation can fail a check and a bad one can pass. I still listened to and read the output.

---

## Latency

All times below are single measurements from my laptop on a home connection, so treat them as rough numbers.

**Before streaming** (one sentence at a time, non-streaming TTS):

| Sentence | ASR | Translation | TTS | Total |
| --- | --- | --- | --- | --- |
| casual | 423 ms | 373 ms | 740 ms | 1535 ms |
| entities | 270 ms | 788 ms | 1104 ms | 2162 ms |
| fast | 273 ms | 278 ms | 599 ms | 1149 ms |
| fillers | 291 ms | 495 ms | 909 ms | 1694 ms |
| meeting | 255 ms | 277 ms | 648 ms | 1180 ms |
| numbers | 277 ms | 582 ms | 1482 ms | 2341 ms |

TTS was the slowest stage every time, and it grew with sentence length.

**After switching to streaming TTS**, for the same sentence:

| | Non-streaming | Streaming |
| --- | --- | --- |
| Time until audio can start playing | 940 ms | 273 ms |
| Time until all audio received | 940 ms | 606 ms |

In live sessions, the first Hindi audio typically arrived 230–450 ms after the translation was ready. Opening the Sarvam connection costs about 300 ms on its own, so it's opened once when the session starts and reused for every sentence.

**Where the time goes now**, roughly, from the moment you stop speaking:

| Stage | Time |
| --- | --- |
| Waiting to be sure you've stopped | 600 ms |
| Speech recognition | 300–550 ms |
| Translation | 350–780 ms |
| First Hindi audio | 230–450 ms |
| **Total** | **about 1.5–2.4 s** |

**The worst case matters too.** In one session, the first speech-recognition request took **4,475 ms**, almost ten times normal. The first request of every session is slower (the connection has to be set up), but this one was extreme. A system that's usually quick but occasionally pauses for five seconds feels unreliable, so a warm-up request at startup and a timeout with retry are high on my to-do list.

---

## Things I learned along the way

- **A fix can create a new problem.** Giving Whisper a prompt with names like "Zoom" and "Slack" fixed "asterisk" → "Asterisk", but on another clip it turned "Howie" into "Javi". A bare list of names primes Whisper to expect names, so I rewrote the prompt as a natural sentence. In one live session, Whisper also produced "Zoom and Slack." when I don't think I'd said it, which looks like it echoing its own prompt.
- **Fluent isn't the same as correct.** "Can we move the meeting to 5pm tomorrow?" kept coming out as "कल की मीटिंग", meaning "tomorrow's meeting", which changes what "tomorrow" refers to. It sounded perfectly natural, which is exactly why it's dangerous. It also translated "move" as "ले जा" (carry). Both are fixed now and have tests.
- **The same company's SDK can use different names for the same thing.** Sarvam's normal TTS call takes `language_code`; the streaming call takes `target_language_code`. I started inspecting function signatures before writing code instead of trusting examples.
- **Silent failures are the worst kind.** A background task in asyncio that crashes doesn't print anything by default. The worker now reports its errors, both in the server log and on the page.

---

## Known limitations

- **Long sessions get cut off.** Vercel closes a WebSocket when the function reaches its maximum duration, a few minutes depending on the plan. When that happens, click Stop and Start again. Automatic reconnecting is the obvious next fix.
- **Speakers cause echo.** Use headphones. With speakers, the mic hears the Hindi audio and can trigger a false interruption.
- **Some recognition errors can't be fixed after the fact.** Without the audio, "Hey Howie" might be a real greeting to someone called Howie, so the translation step can only guess.
- **Tone isn't remembered.** Each sentence is translated on its own, so a casual conversation could occasionally switch to आप.
- **Delay can build up.** If someone talks without stopping, the Hindi takes longer to play than the English took to say, and a backlog grows. I haven't added backlog handling yet.

---

## Running it locally

You'll need API keys from [Groq](https://console.groq.com) and [Sarvam](https://dashboard.sarvam.ai).

```bash
git clone https://github.com/VandanPatel115/voice-translator.git
cd voice-translator
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your keys to .env
uvicorn backend.main:app --reload
```

Open http://localhost:8000 in Chrome, click **Start mic** and allow microphone access. **Use headphones.**

If you installed Python from python.org on a Mac and see `CERTIFICATE_VERIFY_FAILED` when the TTS connects, run the `Install Certificates.command` script in your `/Applications/Python 3.x/` folder once.

To run the translation evaluation (each sentence 5 times):

```bash
python -m tests.eval_translate 5
```

---

## Project structure

```
pyproject.toml     Project settings, including where Vercel finds the app
backend/
  main.py          FastAPI app: WebSocket endpoint, receive loop and the pipeline worker
  vad.py           Silero VAD on ONNX Runtime: speech probability for each 32 ms frame
  models/
    silero_vad.onnx   The VAD model (about 2 MB)
  segmenter.py     Cuts the audio stream into sentences at pauses
  asr.py           Groq Whisper transcription
  preprocess.py    Filler removal, abbreviation expansion, brand-name placeholders
  glossary.json    Names to keep in English and abbreviations to expand
  translate.py     LLM translation with rules, examples and retries
  tts_stream.py    Streaming Hindi TTS from Sarvam
  tts.py           Non-streaming TTS, used by the offline pipeline
  pipeline.py      Offline version: English WAV file in, Hindi WAV file out
frontend/
  index.html
  app.js           Mic capture, WebSocket messages, gapless playback, barge-in
  pcm-worklet.js   Runs on the audio thread and passes mic samples to app.js
tests/
  eval_translate.py   Translation evaluation
```

### WebSocket messages

Binary messages carry audio in both directions. Text messages are JSON events from the server:

| Event | Meaning |
| --- | --- |
| `vad` | The user started or stopped speaking |
| `final_en` | English transcript for a sentence |
| `hindi` | Hindi translation, with ASR and translation times |
| `audio_start` | Hindi audio for a sentence is about to stream; includes the sample rate |
| `audio_end` | That sentence's audio is complete; includes TTS timings |
| `error` | Something failed on the server |

---

## What I'd do next

- **Stream the speech recognition**, so transcription happens while the person is still talking instead of after they stop. Gemini's live transcription API would do this.
- **Stream the translation into TTS** clause by clause, so the first half of the Hindi starts playing before the LLM has finished the second half.
- **Remember the conversation's tone** across sentences.
- **Handle backlogs** by merging waiting sentences into one translation when the speaker doesn't pause.
- **Add a warm-up request and per-stage timeouts** to deal with slow first requests and outliers like the 4.5-second one.
- **Reconnect automatically** with exponential backoff when the connection drops or hits Vercel's time limit.
- **Proper echo cancellation**, so the app works on laptop speakers.