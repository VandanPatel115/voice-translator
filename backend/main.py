import asyncio
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from backend import tts_stream
from backend.asr import transcribe
from backend.segmenter import Segmenter, pcm_to_wav
from backend.translate import translate
from backend.vad import FRAME_BYTES

app = FastAPI()


def report_crash(task: asyncio.Task) -> None:
    """Print the error if a background task fails, instead of failing silently."""
    if not task.cancelled() and task.exception():
        print(f"worker crashed: {task.exception()!r}")


async def process_utterances(queue: asyncio.Queue, ws: WebSocket) -> None:
    """Consumer: ASR → translation → streaming TTS, one utterance at a time."""
    try:
        async with tts_stream.connect() as tts_ws:
            await tts_stream.configure(tts_ws)
            utt_id = 0
            while True:
                pcm = await queue.get()
                utt_id += 1
                try:
                    t0 = time.perf_counter()
                    english = await asyncio.to_thread(transcribe, pcm_to_wav(pcm))
                    t1 = time.perf_counter()
                    await ws.send_json({"type": "final_en", "id": utt_id, "text": english})

                    hindi = await asyncio.to_thread(translate, english)
                    t2 = time.perf_counter()
                    if not hindi:
                        continue
                    await ws.send_json({
                        "type": "hindi", "id": utt_id, "text": hindi,
                        "asr_ms": round((t1 - t0) * 1000),
                        "mt_ms": round((t2 - t1) * 1000),
                    })

                    await ws.send_json({
                        "type": "audio_start", "id": utt_id,
                        "sample_rate": tts_stream.STREAM_SAMPLE_RATE,
                    })
                    t_first = None
                    async for chunk in tts_stream.synthesize_stream(tts_ws, hindi):
                        if t_first is None:
                            t_first = time.perf_counter()
                        await ws.send_bytes(chunk)
                    t3 = time.perf_counter()
                    await ws.send_json({
                        "type": "audio_end", "id": utt_id,
                        "tts_first_ms": round((t_first - t2) * 1000) if t_first else None,
                        "tts_total_ms": round((t3 - t2) * 1000),
                    })
                except Exception as e:
                    print(f"utterance {utt_id} failed: {e!r}")
                    await ws.send_json({
                        "type": "error",
                        "text": f"Sentence {utt_id} failed ({type(e).__name__}), skipping it",
                    })
    except asyncio.CancelledError:
        raise
    except Exception as e:
        await ws.send_json({"type": "error", "text": repr(e)})
        raise


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    print("client connected")

    seg = Segmenter()
    queue: asyncio.Queue = asyncio.Queue()
    worker = asyncio.create_task(process_utterances(queue, ws))
    worker.add_done_callback(report_crash)

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