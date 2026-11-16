import os

import numpy as np
import soundfile as sf
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BYTES_PER_SECOND = 16000 * 2   # 16 kHz × 2 bytes per sample


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    print("client connected")
    audio = bytearray()
    next_report = BYTES_PER_SECOND
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if msg.get("bytes") is not None:
                audio.extend(msg["bytes"])
                if len(audio) >= next_report:
                    seconds = round(len(audio) / BYTES_PER_SECOND, 1)
                    await ws.send_json({"type": "debug", "seconds": seconds})
                    next_report += BYTES_PER_SECOND
            elif msg.get("text") is not None:
                print(f"text: {msg['text']}")
    except WebSocketDisconnect:
        pass
    finally:
        print(f"client disconnected, {len(audio)} bytes received")
        if audio:
            os.makedirs("out", exist_ok=True)
            samples = np.frombuffer(bytes(audio), dtype=np.int16)
            sf.write("out/live_test.wav", samples, 16000, subtype="PCM_16")
            print("saved out/live_test.wav")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")