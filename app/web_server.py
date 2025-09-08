"""Web server hosting control and drawing pages with websocket support."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse  # <-- important

try:  # pragma: no cover - optional dependency
    import websockets
except Exception:  # pragma: no cover
    websockets = None  # type: ignore[assignment]

from app.animation_controller import AnimationControllerThread


HOME_PAGE = """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Alis</title>
<style>
body { font-family: sans-serif; margin:0; }
header { background:#333; color:white; padding:0.5em 1em; display:flex; align-items:center; }
#menu { display:none; flex-direction:column; background:#444; position:absolute; top:3em; left:0; right:0; }
#menu a { color:white; padding:0.5em 1em; text-decoration:none; }
#hamburger { background:none; border:none; color:white; font-size:1.5em; margin-left:auto; }
button { width:80%; padding:1em; font-size:1.2em; margin:1em 0; }
form { display:inline-block; }
</style>
<script>
function toggleMenu(){const m=document.getElementById('menu');m.style.display=m.style.display==='block'?'none':'block';}
</script>
</head>
<body>
<header><h1>Alis</h1><button id="hamburger" onclick="toggleMenu()">☰</button></header>
<nav id="menu"><a href="/">Home</a><a href="/draw">Draw</a></nav>
<div id="content" style="padding:1rem">
<h2>Show</h2>
<form action="/start" method="get"><button type="submit">Start</button></form>
<form action="/stop" method="get"><button type="submit">Stop</button></form>
</div>
</body>
</html>"""

# NOTE: tokens {WS_PORT}, {LED_W}, {LED_H} get replaced via .replace()
DRAW_PAGE = """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Draw</title>
<style>
  body { margin:0; font-family: sans-serif; background:#000; color:#eee; }
  header { background:#333; color:white; padding:.5em 1em; display:flex; align-items:center; }
  #menu { display:none; flex-direction:column; background:#444; position:absolute; top:3em; left:0; right:0; }
  #menu a { color:white; padding:.5em 1em; text-decoration:none; }
  #hamburger { background:none; border:none; color:white; font-size:1.5em; margin-left:auto; }
  #hud { display:flex; gap:.5rem; align-items:center; padding:.5rem 1rem; }
  #pad { width:100vw; height: calc(60vh - 3rem); background:#111; display:block; touch-action:none; }
  #preview { width:100vw; height: 40vh; background:#000; display:block; image-rendering: pixelated; }
  button, input[type=color] { font-size:1rem; padding:.4rem .8rem; }
</style>
<script>
function toggleMenu(){const m=document.getElementById('menu');m.style.display=m.style.display==='block'?'none':'block';}

const WS_PORT = {WS_PORT};
const LED_W = {LED_W};
const LED_H = {LED_H};

let ws, drawing=false, sendQueue=[], lastSent=0;

function hexToRgb(hex){
  const x=hex.replace('#','');
  return [parseInt(x.slice(0,2),16), parseInt(x.slice(2,4),16), parseInt(x.slice(4,6),16)];
}

function setupCanvas(canvas){
  const ctx = canvas.getContext('2d');
  function resize(){
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth;
    const cssH = canvas.clientHeight;
    canvas.width = Math.max(1, Math.floor(cssW * dpr));
    canvas.height = Math.max(1, Math.floor(cssH * dpr));
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.fillStyle = '#111'; ctx.fillRect(0,0,cssW,cssH);
  }
  new ResizeObserver(resize).observe(canvas);
  resize();
  return ctx;
}

function canvasToLed(canvas, clientX, clientY){
  const rect = canvas.getBoundingClientRect();
  const nx = (clientX - rect.left) / rect.width;   // 0..1
  const ny = (clientY - rect.top)  / rect.height;  // 0..1
  let ix = Math.min(LED_W-1, Math.max(0, Math.floor(nx * LED_W)));
  let iy = Math.min(LED_H-1, Math.max(0, Math.floor(ny * LED_H)));
  return [ix, iy];
}

function init(){
  const pad = document.getElementById('pad');
  const preview = document.getElementById('preview');
  const pctx = preview.getContext('2d');
  pctx.imageSmoothingEnabled = false;

  const colorEl = document.getElementById('color');
  const clearBtn = document.getElementById('clear');

  const padCtx = setupCanvas(pad);

  ws = new WebSocket(`ws://${location.hostname}:${WS_PORT}`);
  ws.addEventListener('open', ()=>console.log('ws open'));
  ws.addEventListener('close', ()=>console.log('ws closed'));

  // Local ink feedback on the pad
  function drawDot(x,y,color){
    padCtx.fillStyle = color;
    padCtx.beginPath(); padCtx.arc(x,y,6,0,Math.PI*2); padCtx.fill();
  }

  // Handle pointer input; use coalesced events if available for smoother lines
  function handlePoint(ev){
    const events = (ev.getCoalescedEvents ? ev.getCoalescedEvents() : [ev]);
    const rgb = hexToRgb(colorEl.value);
    const rect = pad.getBoundingClientRect();
    for (const e of events){
      const [ix, iy] = canvasToLed(pad, e.clientX, e.clientY);
      sendQueue.push({x:ix, y:iy, r:rgb[0], g:rgb[1], b:rgb[2]});
      drawDot(e.clientX - rect.left, e.clientY - rect.top, colorEl.value);
    }
  }

  pad.addEventListener('pointerdown', (e)=>{ drawing=true; pad.setPointerCapture(e.pointerId); handlePoint(e); });
  pad.addEventListener('pointermove',  (e)=>{ if (drawing) handlePoint(e); });
  pad.addEventListener('pointerup',    ()=>{ drawing=false; });
  pad.addEventListener('pointercancel',()=>{ drawing=false; });

  // Batch-send ~50 FPS
  function tick(ts){
    if (ws && ws.readyState===1 && sendQueue.length && (!lastSent || ts - lastSent > 20)){
      const pts = sendQueue; sendQueue = []; lastSent = ts;
      ws.send(JSON.stringify({type:"points", pts}));
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);

  clearBtn.addEventListener('click', ()=>{
    if (ws && ws.readyState===1) ws.send(JSON.stringify({type:"clear"}));
    // wipe local pad & preview
    padCtx.fillStyle = '#111'; padCtx.fillRect(0,0,pad.clientWidth,pad.clientHeight);
    pctx.clearRect(0,0,preview.width,preview.height);
  });

  // ---- Preview (server → client) ----
  // We paint LED_W × LED_H pixels into the preview canvas, scaled by CSS.
  function ensurePreviewSize(){
    preview.width = LED_W;
    preview.height = LED_H;
  }
  ensurePreviewSize();

  ws.onmessage = (e)=>{
    const msg = JSON.parse(e.data);
    if (msg.type === 'frame_rle'){
      let idx = 0;
      for (const row of msg.rows){
        for (const run of row){
          const count = run[0]; const rgb = run[1];
          for (let k=0;k<count;k++){
            const x = idx % LED_W;
            const y = Math.floor(idx / LED_W);
            pctx.fillStyle = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
            pctx.fillRect(x, y, 1, 1);
            idx++;
          }
        }
      }
    } else if (msg.type === 'delta'){
      const idxs = msg.indices, rgbs = msg.rgb;
      for (let j=0;j<idxs.length;j++){
        const i = idxs[j], c = rgbs[j];
        const x = i % LED_W;
        const y = Math.floor(i / LED_W);
        pctx.fillStyle = `rgb(${c[0]},${c[1]},${c[2]})`;
        pctx.fillRect(x, y, 1, 1);
      }
    }
  };
}

window.onload = init;
</script>
</head>
<body>
<header><h1>Alis</h1><button id="hamburger" onclick="toggleMenu()">☰</button></header>
<nav id="menu"><a href="/">Home</a><a href="/draw">Draw</a></nav>

<div id="hud">
  <button id="clear">Clear</button>
  <label>Color <input id="color" type="color" value="#00aaff"></label>
</div>

<!-- Touch pad to draw -->
<canvas id="pad"></canvas>

<!-- Live preview of the LED matrix -->
<canvas id="preview"></canvas>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    """Handle basic routing for pages and actions."""

    def do_GET(self) -> None:  # pragma: no cover
        # Normalize the path (strip querystring/fragments) to avoid 404s like /start?x=1
        path = urlparse(self.path).path

        # Quietly ignore favicon lookups
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path.rstrip("/") == "/start":
            self.server.anim_thread.set_mode("animation")  # type: ignore[attr-defined]
            self._redirect("/")
        elif path.rstrip("/") == "/stop":
            self.server.anim_thread.set_mode("static")  # type: ignore[attr-defined]
            self._redirect("/")
        elif path.rstrip("/") == "/draw":
            # Determine matrix size for the pad/preview
            w = h = 16
            try:
                _buf, w, h = self.server.anim_thread.framebuffer_rgb_bytes()  # type: ignore[attr-defined]
            except Exception:
                pass
            html = (DRAW_PAGE
                    .replace("{WS_PORT}", str(self.server.ws_port))      # type: ignore[attr-defined]
                    .replace("{LED_W}", str(w))
                    .replace("{LED_H}", str(h)))
            self._send_html(html)
        elif path == "/":
            self._send_html(HOME_PAGE)
        else:
            self.send_error(404, "Not found")

    def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover
        return

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _send_html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class WebServerThread(threading.Thread):
    """Background server hosting HTTP pages and websocket endpoint."""

    def __init__(
        self,
        stop_evt: threading.Event,
        anim_thread: AnimationControllerThread,
        host: str = "0.0.0.0",
        port: int = 8000,
    ) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.anim_thread = anim_thread
        self.host = host
        self.port = port
        self.ws_port = port + 1
        self.httpd = HTTPServer((host, port), _Handler)
        self.httpd.anim_thread = anim_thread  # type: ignore[attr-defined]
        self.httpd.ws_port = self.ws_port  # type: ignore[attr-defined]
        self.httpd.timeout = 0.5

        self.loop = asyncio.new_event_loop()
        if websockets:
            self.ws_server = websockets.serve(self._ws_handler, host, self.ws_port)
        else:
            self.ws_server = None

        # preview state
        self.clients: set[Any] = set()
        self._last_buf: bytes = b""
        self._last_w: int = 0
        self._last_h: int = 0
        self._fps = 20.0

    # ---------------- Frame diff / compression helpers ----------------
    def _delta_indices(self, old: bytes, new: bytes) -> list[int]:
        if not old or len(old) != len(new):
            return list(range(len(new) // 3))
        diffs = []
        npx = len(new) // 3
        for i in range(npx):
            o = i * 3
            if old[o:o+3] != new[o:o+3]:
                diffs.append(i)
        return diffs

    def _encode_rle_rows(self, buf: bytes, w: int, h: int) -> list[list[tuple[int, list[int]]]]:
        rows = []
        for y in range(h):
            row = []
            start = y * w * 3
            end = start + w * 3
            cur = buf[start:start+3]
            run = 1
            i = start + 3
            while i < end:
                nxt = buf[i:i+3]
                if nxt == cur and run < 255:
                    run += 1
                else:
                    row.append((run, list(cur)))
                    cur = nxt
                    run = 1
                i += 3
            row.append((run, list(cur)))
            rows.append(row)
        return rows

    # ---------------- WebSocket handlers ----------------
    async def _broadcast_loop(self):
        while not self.stop_evt.is_set():
            await asyncio.sleep(1.0 / self._fps)
            if not self.clients:
                continue
            try:
                buf, w, h = self.anim_thread.framebuffer_rgb_bytes()
            except Exception:
                continue
            diffs = self._delta_indices(self._last_buf, buf)
            npx = len(buf) // 3
            use_delta = self._last_w == w and self._last_h == h and 0 < len(diffs) < npx * 0.4
            if use_delta:
                indices = diffs
                rgb = []
                for i in indices:
                    o = i * 3
                    rgb.append([buf[o], buf[o+1], buf[o+2]])
                payload = {"type": "delta", "w": w, "h": h, "indices": indices, "rgb": rgb}
                msg = json.dumps(payload)
            else:
                rle = self._encode_rle_rows(buf, w, h)
                payload = {"type": "frame_rle", "w": w, "h": h, "rows": rle}
                msg = json.dumps(payload)
                self._last_w, self._last_h = w, h
            self._last_buf = buf
            dead = []
            for ws in list(self.clients):
                try:
                    await ws.send(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.clients.discard(ws)

    async def _ws_handler(self, websocket: Any, path: str) -> None:
        # If needed by your AnimationControllerThread, it can still push messages via this 'send'
        send = lambda msg: asyncio.run_coroutine_threadsafe(websocket.send(msg), self.loop)
        self.anim_thread.register_client(send)
        self.clients.add(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    t = data.get("type")
                    if t == "points":
                        # Batch of points: [{x,y,r,g,b}, ...]
                        pts = data.get("pts", [])
                        for p in pts:
                            self.anim_thread.update_pixel(int(p["x"]), int(p["y"]),
                                                          (int(p["r"]), int(p["g"]), int(p["b"])))
                        if hasattr(self.anim_thread, "flush"):
                            self.anim_thread.flush()  # optional
                    elif t == "clear":
                        if hasattr(self.anim_thread, "clear_panel"):
                            self.anim_thread.clear_panel()  # optional API
                        else:
                            # Fallback: paint black across the matrix if size is known
                            try:
                                _buf, w, h = self.anim_thread.framebuffer_rgb_bytes()
                                for yy in range(h):
                                    for xx in range(w):
                                        self.anim_thread.update_pixel(xx, yy, (0,0,0))
                                if hasattr(self.anim_thread, "flush"):
                                    self.anim_thread.flush()
                            except Exception:
                                pass
                    else:
                        # Back-compat: single pixel {x,y,color:"#rrggbb"}
                        if "x" in data and "y" in data and "color" in data:
                            color = data["color"]
                            r = int(color[1:3], 16); g = int(color[3:5], 16); b = int(color[5:7], 16)
                            self.anim_thread.update_pixel(int(data["x"]), int(data["y"]), (r, g, b))
                            if hasattr(self.anim_thread, "flush"):
                                self.anim_thread.flush()
                except Exception:
                    continue
        finally:
            self.anim_thread.unregister_client(send)
            self.clients.discard(websocket)

    # ---------------- Run loop ----------------
    def run(self) -> None:  # pragma: no cover
        ws = None
        if websockets and self.ws_server:
            asyncio.set_event_loop(self.loop)
            ws = self.loop.run_until_complete(self.ws_server)
            self.loop.create_task(self._broadcast_loop())
        print(f"[Web] server listening on {self.host}:{self.port}")
        while not self.stop_evt.is_set():
            self.httpd.handle_request()
            if websockets and self.ws_server:
                self.loop.run_until_complete(asyncio.sleep(0.05))
        self.httpd.server_close()
        if ws:
            ws.close()
            self.loop.run_until_complete(ws.wait_closed())
            self.loop.close()
        print("[Web] server stopped")
