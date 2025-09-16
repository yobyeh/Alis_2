#hardcoding 16x16 for testing , needs to get from passed settings or somthing
#may not need to send color change msg any more 
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from multiprocessing import Queue
import shutil
from pathlib import Path

app = FastAPI()
web_animation_queue = None

# Mount the /web directory for static files
app.mount("/web", StaticFiles(directory="web"), name="web")

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("web/home.html") as f:
        return HTMLResponse(f.read())

@app.post("/api/drawmode")
async def draw_mode():
    print("Draw mode activated!", flush=True)
    return {"status": "draw mode"}

@app.websocket("/wsdraw")
async def ws_draw(websocket: WebSocket):
    await websocket.accept()
    web_animation_queue = app.state.web_animation_queue
    while True:
        data = await websocket.receive_text()
        try:
            import json
            msg = json.loads(data)
            if msg.get("type") == "color":
                print(f"Color changed to {msg['color']}", flush=True)
            elif msg.get("type") == "matrix":
                print("Received matrix", flush=True)
                web_animation_queue.put(msg)  # Send the whole matrix to animation controller
            elif msg.get("type") == "clear":
                print("Clear canvas", flush=True)
                web_animation_queue.put("clear")
        except Exception as e:
            print("WebSocket error:", e, flush=True)
            await websocket.send_text("Error: invalid data")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    raw_folder = Path("uploaded/raw")
    raw_folder.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "uploaded_file"
    file_path = raw_folder / filename
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": filename}

if __name__ == "__main__":
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True)

