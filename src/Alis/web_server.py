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
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure preview directory exists before mounting
Path("uploaded/images/preview").mkdir(parents=True, exist_ok=True)

import threading

app = FastAPI()

# Global cache for current settings
current_settings_cache = {}

# Background thread to monitor interface_web_queue
def interface_settings_monitor():
    import time
    while True:
        try:
            if hasattr(app.state, "interface_web_queue") and app.state.interface_web_queue:
                try:
                    print("int web que msg", flush=True)
                    msg = app.state.interface_web_queue.get_nowait()
                    if isinstance(msg, dict) and msg.get("type") == "settings_update":
                        settings = msg.get("settings")
                        if isinstance(settings, dict):
                            print(f"[web_server] Received settings_update: {settings}", flush=True)
                            current_settings_cache.clear()
                            current_settings_cache.update(settings)
                            print(f"[web_server] Updated current_settings_cache: {current_settings_cache}", flush=True)
                except Exception:
                    pass
        except Exception as e:
            print(f"[web_server] Error in interface_settings_monitor: {e}", flush=True)
        time.sleep(0.2)

# Start the background thread on startup
@app.on_event("startup")
def start_settings_monitor():
    print("starting monitor thread")
    t = threading.Thread(target=interface_settings_monitor, daemon=True)
    t.start()
preview_dir = os.path.join(BASE_DIR, "uploaded", "images", "preview")
app.mount("/web/images/preview", StaticFiles(directory=preview_dir), name="preview")
app.mount("/web/animations/preview", StaticFiles(directory="uploaded/animations/preview"), name="preview")
app.mount("/web", StaticFiles(directory="web"), name="web")
assets_dir = os.path.join(BASE_DIR, "assets")
app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

@app.get("/", response_class=HTMLResponse)
async def home():
    home_html = os.path.join(BASE_DIR, "web", "home.html")
    with open(home_html) as f:
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
                # if msg.get("type") == "color":
                #     print(f"Color changed to {msg['color']}", flush=True)
                if msg.get("type") == "matrix":
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

@app.post("/api/run_text")
async def run_text(data: dict = Body(...)):
    # Switch animation controller to text mode
    web_animation_queue = app.state.web_animation_queue
    msg = {"type": "mode", "mode": "text"}
    web_animation_queue.put(msg)
    print("Sent text mode message to animation controller")

    # Send text entry name
    name = data.get("name")
    print(f"Run text requested: {name}")
    web_animation_queue.put({"type": "text", "name": name})
    return {"status": "ok", "name": name}

@app.post("/api/test_text")
async def test_text(data: dict = Body(...)):
    # Switch animation controller to text mode
    web_animation_queue = app.state.web_animation_queue
    msg = {"type": "mode", "mode": "text"}
    web_animation_queue.put(msg)
    print("Sent text mode message to animation controller (test)")

    # Send all text parameters directly
    print(f"Test text requested: {data}")
    web_animation_queue.put({"type": "text_test", **data})
    return {"status": "ok", "data": data}

@app.get("/api/shows_list")
async def shows_list():
    import json
    shows_path = os.path.join(BASE_DIR, "data", "shows.json")
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
    web_animation_queue.put({"type": "mode", "mode": "show"})
    web_animation_queue.put({"type": "show_entry", "data": data})
    return {"status": "ok"}

@app.get("/api/text_list")
async def text_list():
    import json
    text_path = os.path.join(BASE_DIR, "data", "text_display.json")
    text_path = Path("data/text_display.json")
    if not text_path.exists():
        return JSONResponse([])
    with open(text_path, "r") as f:
        text_data = json.load(f)
    return JSONResponse(text_data)

@app.post("/api/save_show")
async def save_show(data: dict = Body(...)):
    import json
    shows_path = os.path.join(BASE_DIR, "data", "shows.json")
    shows_path = Path("data/shows.json")
    # Load existing shows
    if shows_path.exists():
        with open(shows_path, "r") as f:
            shows_data = json.load(f)
    else:
        shows_data = {"shows": []}
    # Check for duplicate name
    for idx, show in enumerate(shows_data["shows"]):
        if show["name"] == data["name"]:
            return JSONResponse({"error": "Show name already exists."}, status_code=400)
    # Add or update show
    shows_data["shows"].append(data)
    with open(shows_path, "w") as f:
        json.dump(shows_data, f, indent=2)
    return {"status": "saved"}

@app.post("/api/delete_show")
async def delete_show(data: dict = Body(...)):
    import json
    shows_path = os.path.join(BASE_DIR, "data", "shows.json")
    shows_path = Path("data/shows.json")
    if not shows_path.exists():
        return JSONResponse({"error": "No shows file."}, status_code=404)
    with open(shows_path, "r") as f:
        shows_data = json.load(f)
    shows_data["shows"] = [s for s in shows_data["shows"] if s["name"] != data.get("name")]
    with open(shows_path, "w") as f:
        json.dump(shows_data, f, indent=2)
    return {"status": "deleted"}

@app.post("/api/save_text_entry")
async def save_text_entry(data: dict = Body(...)):
    import json
    text_path = os.path.join(BASE_DIR, "data", "text_display.json")
    text_path = Path("data/text_display.json")
    # Load existing entries
    if text_path.exists():
        with open(text_path, "r") as f:
            text_data = json.load(f)
    else:
        text_data = []
    # Check for duplicate name
    for entry in text_data:
        if entry.get("name") == data["name"]:
            return JSONResponse({"error": "Text name already exists."}, status_code=400)
    text_data.append(data)
    with open(text_path, "w") as f:
        json.dump(text_data, f, indent=2)
    return {"status": "saved"}

@app.post("/api/run_show")
async def run_show(data: dict = Body(...)):
    # Send play_show message to ShowController
    show_name = data.get("name")
    print(f"Run show requested: {show_name}")
    web_show_queue = app.state.web_show_queue  # You need to set this up in your app
    web_show_queue.put({"type": "play_show", "name": show_name})
    return {"status": "ok", "name": show_name}

# Endpoint: /api/update_setting
# This endpoint receives a POST request with JSON:
# {
#   "setting": "LED Brightness",
#   "value": 3
# }
# When a dropdown value is changed on the frontend, send this request.
# The backend should:
#   - Acquire settings_lock
#   - Update current_settings[setting] = value
#   - Optionally send a message to the relevant controller/queue if needed
#   - Release settings_lock
#   - Return success

@app.post("/api/update_setting")
async def update_setting(request: Request):
    # Parse the incoming JSON
    data = await request.json()
    setting = data.get("setting")
    value = data.get("value")

    # Send message to web_interface_event queue if available
    msg = {"type": "settings_change", "setting": setting, "value": value}
    if hasattr(app.state, "web_interface_event") and app.state.web_interface_event:
        try:
            app.state.web_interface_event.put(msg)
        except Exception as e:
            print(f"Failed to put message on web_interface_event: {e}", flush=True)
    else:
        print("web_interface_event queue not available in app.state", flush=True)
    return {"status": "ok"}

@app.get("/api/settings_options")
async def settings_options():
    import json
    menu_path = os.path.join(BASE_DIR, "data", "menu_data.json")
    with open(menu_path, "r") as f:
        menu_data = json.load(f)
    # Get all settings under "home" > "Settings"
    settings_section = menu_data.get("home", {}).get("Settings", {})
    settings_list = []
    for name, info in settings_section.items():
        settings_list.append({
            "name": name,
            "options": info.get("options", []),
            "default": info.get("default", None),
            "action": info.get("action", ""),
        })
    # Return both the menu layout and the latest current settings
    return JSONResponse({
        "settings": settings_list,
        "current": dict(current_settings_cache)
    })

if __name__ == "__main__":
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True)

