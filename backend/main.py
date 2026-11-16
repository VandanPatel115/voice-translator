from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

app = FastAPI()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    print("client connected")
    try:
        while True:
            msg = await ws.receive_text()
            print(f"received: {msg}")
            await ws.send_text(f"server got: {msg}")
    except WebSocketDisconnect:
        print("client disconnected")

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")