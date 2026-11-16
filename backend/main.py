import asyncio
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend.asr import transcribe
from backend.segmenter import Segmenter, pcm_to_wav
from backend.translate import translate
from backend.vad import FRAME_BYTES, reset

app = FastAPI()


async def process_utterances(queue: asyncio.Queue, ws: WebSocket) -> None:
    """Consumer: take finished utterances and run ASR, then translation."""
    utt_id = 0
    while True:
        pcm = await queue.get()
        utt_id += 1

        t0 = time.perf_counter()
        english = await asyncio.to_thread(transcribe, pcm_to_wav(pcm))
        t1 = time.perf_counter()
        await ws.send_json({"type": "final_en", "id": utt_id, "text": english})

        hindi = await asyncio.to_thread(translate, english)
        t2 = time.perf_counter()
        await ws.send_json({
            "type": "hindi",
            "id": utt_id,
            "text": hindi,
            "asr_ms": round((t1 - t0) * 1000),
            "mt_ms": round((t2 - t1) * 1000),
        })


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    print("client connected")

    reset()
    seg = Segmenter()
    queue: asyncio.Queue = asyncio.Queue()
    worker = asyncio.create_task(process_utterances(queue, ws))

    buffer = b""
    was_speaking = False
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is None:
                continue

            buffer += msg["bytes"]
            while len(buffer) >= FRAME_BYTES:
                frame, buffer = buffer[:FRAME_BYTES], buffer[FRAME_BYTES:]
                utterance = seg.feed(frame)
                if utterance:
                    await queue.put(utterance)

                speaking = seg.state == "SPEAKING"
                if speaking != was_speaking:
                    await ws.send_json({"type": "vad", "speaking": speaking})
                    was_speaking = speaking
    except WebSocketDisconnect:
        pass
    finally:
        worker.cancel()
        print("client disconnected")


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")