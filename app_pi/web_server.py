#hardcoding 16x16 for testing , needs to get from passed settings or somthing
#may not need to send color change msg any more 
from fastapi import FastAPI, WebSocket, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Body
import uvicorn
from multiprocessing import Queue, Process
import shutil
from pathlib import Path
from matrix_convert import run_matrix_convert
import h5py

# Ensure preview directory exists before mounting
Path("uploaded/images/preview").mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/web/images/preview", StaticFiles(directory="uploaded/images/preview"), name="preview")
app.mount("/web/animations/preview", StaticFiles(directory="uploaded/animations/preview"), name="preview")
app.mount("/web", StaticFiles(directory="web"), name="web")
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("web/home.html") as f:
        return HTMLResponse(f.read())

@app.get("/api/image_list")
async def image_list():
    preview_folder = Path("uploaded/images/preview")
    image_folder = Path("uploaded/images")
    items = []
    for h5_file in image_folder.glob("*.h5"):
        name = h5_file.name
        preview_file = preview_folder / (h5_file.stem + ".png")
        preview_url = f"/web/images/preview/{preview_file.name}" if preview_file.exists() else ""
        # Read matrix_size from HDF5 metadata
        with h5py.File(h5_file, "r") as h5f:
            height, width = h5f.attrs["matrix_size"]
            height = int(height)
            width = int(width)
        items.append({
            "name": name,
            "preview_url": preview_url,
            "height": height,
            "width": width
        })
    return JSONResponse(items)

@app.get("/api/animation_list")
async def animation_list():
    preview_folder = Path("uploaded/animations/preview")
    animation_folder = Path("uploaded/animations")
    items = []
    for h5_file in animation_folder.glob("*.h5"):
        name = h5_file.name
        preview_file = preview_folder / (h5_file.stem + ".png")
        preview_url = f"/web/animations/preview/{preview_file.name}" if preview_file.exists() else ""
        with h5py.File(h5_file, "r") as h5f:
            height, width = h5f.attrs["matrix_size"]
            height = int(height)
            width = int(width)
        items.append({
            "name": name,
            "preview_url": preview_url,
            "height": height,
            "width": width
        })
    return JSONResponse(items)

@app.post("/api/drawmode")
async def draw_mode():
    web_animation_queue = app.state.web_animation_queue
    msg = {"type": "mode", "mode": "draw"}
    web_animation_queue.put(msg)
    print("Sent draw mode message to animation controller")
    return {"status": "draw mode"}

@app.websocket("/wsdraw")
async def ws_draw(websocket: WebSocket):
    await websocket.accept()
    web_animation_queue = app.state.web_animation_queue
    try:
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
    except Exception as e:
        print(f"WebSocket closed: {e}", flush=True)

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    raw_folder = Path("uploaded/raw")
    raw_folder.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "uploaded_file"
    file_path = raw_folder / filename
    with open(file_path, "wb") as buffer:  # Use built-in open()
        shutil.copyfileobj(file.file, buffer)
    proc = Process(target=run_matrix_convert, kwargs={"grb": True})
    proc.start()
    return {"filename": filename}

@app.post("/api/run_image")
async def run_image(data: dict = Body(...)):
    #switch animation controller to static mode
    web_animation_queue = app.state.web_animation_queue
    msg = {"type": "mode", "mode": "static"}
    web_animation_queue.put(msg)
    print("Sent static mode message to animation controller")

    #send image
    name = data.get("name")
    print(f"Run image requested: {name}")
    web_animation_queue = app.state.web_animation_queue
    web_animation_queue.put({"type": "image", "name": name})
    return {"status": "ok", "name": name}

@app.post("/api/run_animation")
async def run_animation(data: dict = Body(...)):
    # Switch animation controller to animation mode
    web_animation_queue = app.state.web_animation_queue
    msg = {"type": "mode", "mode": "animation"}
    web_animation_queue.put(msg)
    print("Sent animation mode message to animation controller")

    # Send animation file name
    name = data.get("name")
    print(f"Run animation requested: {name}")
    web_animation_queue.put({"type": "animation", "name": name})
    return {"status": "ok", "name": name}

@app.get("/api/shows_list")
async def shows_list():
    import json
    shows_path = Path("data/shows.json")
    if not shows_path.exists():
        return JSONResponse({"shows": []})
    with open(shows_path, "r") as f:
        shows_data = json.load(f)
    return JSONResponse(shows_data)

@app.post("/api/run_show_entry")
async def run_show_entry(data: dict = Body(...)):
    # You can use show_index, entry_index, or entry data to send a message to the animation controller
    print(f"Show entry selected: {data}")
    # Example: send to animation controller queue
    web_animation_queue = app.state.web_animation_queue
    web_animation_queue.put({"type": "show_entry", "data": data})
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True)

