#hardcoding 16x16 for testing , needs to get from passed settings or somthing
#may not need to send color change msg any more 
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
from multiprocessing import Queue

app = FastAPI()
web_animation_queue = None

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mobile Draw</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; margin: 0; padding: 0; background: #fafafa; }
            #container { display: flex; flex-direction: column; height: 100vh; }
            #drawCanvas {
                display: block;
                margin: 0 auto;
                border: 2px solid #333;
                background: #fff;
                touch-action: none;
                width: 600px;
                height: 600px;
                max-width: 100vw;
                max-height: 60vh;
            }
            #controls {
                display: flex;
                flex-direction: row;
                align-items: center;
                justify-content: center;
                padding: 20px 0 10px 0;
                background: #f0f0f0;
                gap: 20px;
            }
            #colorPicker { width: 120px; height: 60px; }
            #clearBtn { padding: 18px 32px; font-size: 1.2em; }
            #buttonDraw { width: 90vw; max-width: 500px; padding: 30px; font-size: 2em; margin: 10px auto 0 auto; display: block; }
        </style>
    </head>
    <body>
        <div id="container">
            <canvas id="drawCanvas" width="600" height="600"></canvas>
            <div id="controls">
                <input type="color" id="colorPicker" value="#ff0000">
                <button id="clearBtn">Clear Canvas</button>
            </div>
            <button id="buttonDraw">Restart Draw Mode</button>
        </div>
        <script>
            let ws = null;
            let color = "#ff0000";
            const button = document.getElementById("buttonDraw");
            const colorPicker = document.getElementById("colorPicker");
            const clearBtn = document.getElementById("clearBtn");
            const canvas = document.getElementById("drawCanvas");
            const size = Math.min(window.innerWidth, window.innerHeight * 0.6, 600);
            canvas.width = size;
            canvas.height = size;
            canvas.style.width = size + "px";
            canvas.style.height = size + "px";
            const ctx = canvas.getContext("2d");
            let drawing = false;
            let lastSent = 0;

            function startWebSocket() {
                if (ws) {
                    ws.close();
                }
                ws = new WebSocket("ws://" + location.host + "/wsdraw");
                ws.onopen = () => console.log("WebSocket started");
                ws.onmessage = (msg) => console.log("Server:", msg.data);
            }

            button.onclick = () => {
                console.log("draw mode");
                fetch("/api/drawmode", {method: "POST"});
                startWebSocket();
            };

            window.onload = () => {
                startWebSocket();
            };

            colorPicker.oninput = (e) => {
                color = colorPicker.value;
                if (ws && ws.readyState === 1) {
                    ws.send(JSON.stringify({type: "color", color: color}));
                }
            };

            clearBtn.onclick = () => {
                // Clear the canvas visually
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                // Send clear message to backend
                if (ws && ws.readyState === 1) {
                    ws.send(JSON.stringify({type: "clear"}));
                }
                // TODO: Hook up to other backend code here for full LED clear
            };

            function sendDraw(x, y) {
                const now = Date.now();
                if (now - lastSent < 50) return; // Only send every x ms
                lastSent = now;
                let mx = Math.round(x / canvas.width * 100);
                let my = Math.round(y / canvas.height * 100);
                if (ws && ws.readyState === 1) {
                    ws.send(JSON.stringify({type: "draw", x: mx, y: my, color: color}));
                }
            }

            canvas.addEventListener("mousedown", e => {
                drawing = true;
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 12, 0, 2 * Math.PI);
                ctx.fill();
                // sendDraw(x, y);  // <--- REMOVE THIS LINE
            });

            canvas.addEventListener("mousemove", e => {
                if (!drawing) return;
                const rect = canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 12, 0, 2 * Math.PI);
                ctx.fill();
                // sendDraw(x, y);  // <--- REMOVE THIS LINE
            });

            canvas.addEventListener("mouseup", e => {
                drawing = false;
                sendMatrix();
            });
            canvas.addEventListener("mouseleave", e => {
                drawing = false;
                sendMatrix();
            });

            // Touch support
            canvas.addEventListener("touchstart", e => {
                drawing = true;
                const rect = canvas.getBoundingClientRect();
                const touch = e.touches[0];
                const x = touch.clientX - rect.left;
                const y = touch.clientY - rect.top;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 12, 0, 2 * Math.PI);
                ctx.fill();
                // sendDraw(x, y);  // <--- REMOVE THIS LINE
            });
            canvas.addEventListener("touchmove", e => {
                if (!drawing) return;
                const rect = canvas.getBoundingClientRect();
                const touch = e.touches[0];
                const x = touch.clientX - rect.left;
                const y = touch.clientY - rect.top;
                ctx.fillStyle = color;
                ctx.beginPath();
                ctx.arc(x, y, 12, 0, 2 * Math.PI);
                ctx.fill();
                // sendDraw(x, y);  // <--- REMOVE THIS LINE
                e.preventDefault();
            });
            canvas.addEventListener("touchend", e => {
                drawing = false;
                sendMatrix();
            });
            canvas.addEventListener("touchcancel", e => {
                drawing = false;
                sendMatrix();
            });

            function getMatrix(gridW, gridH) {
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
                const matrix = [];
                const cellW = canvas.width / gridW;
                const cellH = canvas.height / gridH;
                for (let gx = 0; gx < gridW; gx++) {
                    const row = [];
                    for (let gy = 0; gy < gridH; gy++) {
                        // Sample center pixel of each cell
                        const px = Math.floor((gx + 0.5) * cellW);
                        const py = Math.floor((gy + 0.5) * cellH);
                        const idx = (py * canvas.width + px) * 4;
                        const r = imageData[idx];
                        const g = imageData[idx + 1];
                        const b = imageData[idx + 2];
                        row.push([r, g, b]);
                    }
                    matrix.push(row);
                }
                return matrix;
            }

            function sendMatrix() {
                const matrix = getMatrix(16, 16); // or your grid size
                if (ws && ws.readyState === 1) {
                    ws.send(JSON.stringify({type: "matrix", matrix: matrix}));
                }
            }
        </script>
    </body>
    </html>
    """

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

if __name__ == "__main__":
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=True)

