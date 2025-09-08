"""Web server hosting control and drawing pages with websocket support."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

try:  # pragma: no cover - optional dependency
    import websockets
except Exception:  # pragma: no cover
    websockets = None  # type: ignore[assignment]

from app.animation_controller import AnimationControllerThread


HOME_PAGE = """<!doctype html>
<html>
<head>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Alis</title>
<style>
body { font-family: sans-serif; margin:0; }
header { background:#333; color:white; padding:0.5em 1em; display:flex; align-items:center; }
#menu { display:none; flex-direction:column; background:#444; position:absolute; top:3em; left:0; right:0; }
#menu a { color:white; padding:0.5em 1em; text-decoration:none; }
#hamburger { background:none; border:none; color:white; font-size:1.5em; margin-left:auto; }
button { width:80%; padding:1em; font-size:1.2em; margin:1em 0; }
</style>
<script>
function toggleMenu(){const m=document.getElementById('menu');m.style.display=m.style.display=='block'?'none':'block';}
</script>
</head>
<body>
<header><h1>Alis</h1><button id=\"hamburger\" onclick=\"toggleMenu()\">☰</button></header>
<nav id=\"menu\"><a href=\"/\">Home</a><a href=\"/draw\">Draw</a></nav>
<div id=\"content\">
<h2>Show</h2>
<form action=\"/start\" method=\"get\"><button type=\"submit\">Start</button></form>
<form action=\"/stop\" method=\"get\"><button type=\"submit\">Stop</button></form>
</div>
</body>
</html>"""

DRAW_PAGE = """<!doctype html>
<html>
<head>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>Draw</title>
<style>
body { font-family: sans-serif; margin:0; }
header { background:#333; color:white; padding:0.5em 1em; display:flex; align-items:center; }
#menu { display:none; flex-direction:column; background:#444; position:absolute; top:3em; left:0; right:0; }
#menu a { color:white; padding:0.5em 1em; text-decoration:none; }
#hamburger { background:none; border:none; color:white; font-size:1.5em; margin-left:auto; }
.grid { display:grid; grid-template-columns:repeat(16,20px); grid-template-rows:repeat(16,20px); margin:1em; }
.cell { width:20px; height:20px; border:1px solid #555; }
.palette { margin:1em; }
.swatch { width:20px; height:20px; display:inline-block; margin:0 5px; cursor:pointer; border:1px solid #000; }
</style>
<script>
function toggleMenu(){const m=document.getElementById('menu');m.style.display=m.style.display=='block'?'none':'block';}
const WS_PORT={ws_port};
let current='#ff0000';
let drawing=false;
function init(){
  const grid=document.getElementById('grid');
  for(let y=0;y<16;y++){
    for(let x=0;x<16;x++){
      const c=document.createElement('div');c.className='cell';c.dataset.x=x;c.dataset.y=y;
      c.addEventListener('mousedown',paint);
      c.addEventListener('mouseover',e=>{if(drawing)paint(e);});
      grid.appendChild(c);
    }
  }
  grid.addEventListener('mousedown',()=>{drawing=true;});
  document.addEventListener('mouseup',()=>{drawing=false;});
  const palette=document.getElementById('palette');
  ['#ff0000','#00ff00','#0000ff','#ffffff','#000000'].forEach(col=>{
    const s=document.createElement('div');s.className='swatch';s.style.background=col;
    s.addEventListener('click',()=>{current=col;});palette.appendChild(s);});
  const ws=new WebSocket(`ws://${location.hostname}:${WS_PORT}`);
  ws.onmessage=e=>{
    const data=JSON.parse(e.data).frame;
    const cells=grid.children;
    for(let y=0;y<16;y++){
      for(let x=0;x<16;x++){
        const idx=y*16+x;
        const rgb=data[y][x];
        cells[idx].style.background=`rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
      }
    }
  };
  window._ws=ws;
}
function paint(e){
  const cell=e.target;cell.style.background=current;
  if(window._ws && window._ws.readyState===1){
    window._ws.send(JSON.stringify({x:parseInt(cell.dataset.x),y:parseInt(cell.dataset.y),color:current}));
  }
}
window.onload=init;
</script>
</head>
<body>
<header><h1>Alis</h1><button id=\"hamburger\" onclick=\"toggleMenu()\">☰</button></header>
<nav id=\"menu\"><a href=\"/\">Home</a><a href=\"/draw\">Draw</a></nav>
<div id=\"content\">
<div id=\"grid\" class=\"grid\"></div>
<div id=\"palette\" class=\"palette\"></div>
</div>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    """Handle basic routing for pages and actions."""

    def do_GET(self) -> None:  # pragma: no cover - trivial routing
        if self.path == "/start":
            self.server.anim_thread.set_mode("animation")  # type: ignore[attr-defined]
            self._redirect("/")
        elif self.path == "/stop":
            self.server.anim_thread.set_mode("static")  # type: ignore[attr-defined]
            self._redirect("/")
        elif self.path == "/draw":
            html = DRAW_PAGE.format(ws_port=self.server.ws_port)  # type: ignore[attr-defined]
            self._send_html(html)
        elif self.path == "/":
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

    async def _ws_handler(self, websocket: Any, path: str) -> None:  # pragma: no cover - network
        send = lambda msg: asyncio.run_coroutine_threadsafe(websocket.send(msg), self.loop)
        self.anim_thread.register_client(send)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    color = data.get("color", "#000000")
                    r = int(color[1:3], 16)
                    g = int(color[3:5], 16)
                    b = int(color[5:7], 16)
                    self.anim_thread.update_pixel(int(data.get("x", 0)), int(data.get("y", 0)), (r, g, b))
                except Exception:
                    continue
        finally:
            self.anim_thread.unregister_client(send)

    def run(self) -> None:  # pragma: no cover - contains blocking loop
        ws = None
        if websockets and self.ws_server:
            asyncio.set_event_loop(self.loop)
            ws = self.loop.run_until_complete(self.ws_server)
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
