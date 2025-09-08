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

# NOTE: we will replace the literal token {WS_PORT} with the actual port via .replace()
DRAW_PAGE = """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Draw</title>
<style>
body { font-family: sans-serif; margin:0; }
header { background:#333; color:white; padding:0.5em 1em; display:flex; align-items:center; }
#menu { display:none; flex-direction:column; background:#444; position:absolute; top:3em; left:0; right:0; }
#menu a { color:white; padding:0.5em 1em; text-decoration:none; }
#hamburger { background:none; border:none; color:white; font-size:1.5em; margin-left:auto; }
.grid { display:grid; grid-template-columns:repeat(16,20px); grid-template-rows:repeat(16,20px); margin:1em; touch-action:none; }
.cell { width:20px; height:20px; border:1px solid #555; }
.palette { margin:1em; }
.swatch { width:20px; height:20px; display:inline-block; margin:0 5px; cursor:pointer; border:1px solid #000; }
</style>
<script>
function toggleMenu(){const m=document.getElementById('menu');m.style.display=m.style.display==='block'?'none':'block';}
const WS_PORT={WS_PORT};
let current='#ff0000';
let drawing=false;
function init(){
  const grid=document.getElementById('grid');
  for(let y=0;y<16;y++){
    for(let x=0;x<16;x++){
      const c=document.createElement('div');c.className='cell';c.dataset.x=x;c.dataset.y=y;
      c.addEventListener('pointerdown',paint);
      c.addEventListener('pointermove',e=>{if(drawing)paint(e);});
      grid.appendChild(c);
    }
  }
  grid.addEventListener('pointerdown',()=>{drawing=true;});
  document.addEventListener('pointerup',()=>{drawing=false;});
  const palette=document.getElementById('palette');
  ['#ff0000','#00ff00','#0000ff','#ffffff','#000000'].forEach(col=>{
    const s=document.createElement('div');s.className='swatch';s.style.background=col;
    s.addEventListener('click',()=>{current=col;});palette.appendChild(s);});
  const ws=new WebSocket(`ws://${location.hostname}:${WS_PORT}`);
  ws.onmessage=e=>{
    const msg=JSON.parse(e.data);
    const cells=grid.children;
    if(msg.type==='frame_rle'){
      let idx=0;
      for(const row of msg.rows){
        for(const run of row){
          const count=run[0];const rgb=run[1];
          for(let k=0;k<count;k++){
            if(idx<cells.length)cells[idx].style.background=`rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
            idx++;
          }
        }
      }
    } else if(msg.type==='delta'){
      for(let j=0;j<msg.indices.length;j++){
        const i=msg.indices[j];
        const c=msg.rgb[j];
        if(i<cells.length)cells[i].style.background=`rgb(${c[0]},${c[1]},${c[2]})`;
      }
    }
  };
  window._ws=ws;
}
function paint(e){
  const cell=e.target;if(!cell.dataset)return;
  cell.style.background=current;
  if(window._ws && window._ws.readyState===1){
    window._ws.send(JSON.stringify({x:parseInt(cell.dataset.x),y:parseInt(cell.dataset.y),color:current}));
  }
}
window.onload=init;
</script>
</head>
<body>
<header><h1>Alis</h1><button id="hamburger" onclick="toggleMenu()">☰</button></header>
<nav id="menu"><a href="/">Home</a><a href="/draw">Draw</a></nav>
<div id="content">
<div id="grid" class="grid"></div>
<div id="palette" class="palette"></div>
</div>
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
            # Avoid str.format() so CSS/JS braces don't break — just replace the token.
            html = DRAW_PAGE.replace("{WS_PORT}", str(self.server.ws_port))  # type: ignore[attr-defined]
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
        send = lambda msg: asyncio.run_coroutine_threadsafe(websocket.send(msg), self.loop)
        self.anim_thread.register_client(send)
        self.clients.add(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    color = data.get("color", "#000000")
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    self.anim_thread.update_pixel(
                        int(data.get("x", 0)),
                        int(data.get("y", 0)),
                        (r, g, b),
                    )
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
