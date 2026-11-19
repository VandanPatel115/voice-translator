import asyncio
import base64
import os
import sys
import time

import numpy as np
import soundfile as sf
from dotenv import load_dotenv
from sarvamai import AsyncSarvamAI, AudioOutput, EventResponse

load_dotenv()

STREAM_SAMPLE_RATE = 22050

client = AsyncSarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])


def connect():
    """Open a streaming TTS connection (use with 'async with')."""
    return client.text_to_speech_streaming.connect(
        model="bulbul:v3", send_completion_event="true"
    )


async def configure(ws) -> None:
    await ws.configure(
        target_language_code="hi-IN",
        speaker="shubh",
        output_audio_codec="linear16",
        speech_sample_rate=STREAM_SAMPLE_RATE,
    )


async def synthesize_stream(ws, text: str):
    """Send Hindi text, then yield raw PCM chunks until the sentence is finished."""
    await ws.convert(text)
    await ws.flush()
    leftover = b""
    while True:
        message = await ws.recv()
        if isinstance(message, AudioOutput):
            data = leftover + base64.b64decode(message.data.audio)
            if len(data) % 2:
                data, leftover = data[:-1], data[-1:]
            else:
                leftover = b""
            if data:
                yield data
        elif isinstance(message, EventResponse) and message.data.event_type == "final":
            return

async def stream_test(text: str) -> None:
    client = AsyncSarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])

    t0 = time.perf_counter()
    async with client.text_to_speech_streaming.connect(
        model="bulbul:v3", send_completion_event="true"
    ) as ws:
        t_connected = time.perf_counter()

        await ws.configure(
            target_language_code="hi-IN",
            speaker="shubh",
            output_audio_codec="linear16",
            speech_sample_rate=STREAM_SAMPLE_RATE,
        )
        await ws.convert(text)
        await ws.flush()
        t_sent = time.perf_counter()

        chunks: list[bytes] = []
        t_first = None
        async for message in ws:
            if isinstance(message, AudioOutput):
                chunk = base64.b64decode(message.data.audio)
                if t_first is None:
                    t_first = time.perf_counter()
                    print(f"first chunk: {len(chunk)} bytes, starts with {chunk[:4]!r}")
                chunks.append(chunk)
            elif isinstance(message, EventResponse):
                print(f"event: {message}")
                break
            else:
                print(f"other message: {type(message).__name__}: {message}")

    t_done = time.perf_counter()
    ms = lambda a, b: (b - a) * 1000
    pcm = b"".join(chunks)

    print(f"connect:          {ms(t0, t_connected):.0f} ms")
    print(f"first audio:      {ms(t_sent, t_first):.0f} ms after sending text")
    print(f"all audio:        {ms(t_sent, t_done):.0f} ms after sending text")
    print(f"chunks:           {len(chunks)}, {len(pcm)} bytes, "
          f"{len(pcm) / (STREAM_SAMPLE_RATE * 2):.2f} s of audio")

    os.makedirs("out", exist_ok=True)
    sf.write("out/stream_test.wav", np.frombuffer(pcm, dtype=np.int16),
             STREAM_SAMPLE_RATE, subtype="PCM_16")
    print("saved out/stream_test.wav")


if __name__ == "__main__":
    sentence = sys.argv[1] if len(sys.argv) > 1 else \
        "क्या हम मीटिंग को कल शाम 5 बजे कर सकते हैं?"
    asyncio.run(stream_test(sentence))