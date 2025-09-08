"""Simple web server thread to control the LED test via a phone.

This module exposes :class:`WebServerThread` which hosts a minimal web page
with *Start* and *Stop* buttons.  When the buttons are pressed the server
invokes :meth:`LEDThread.set_pattern` on the provided LED thread.

The server listens on all interfaces so the page can be opened from a phone on
the same network.  It is intentionally lightweight and avoids external
dependencies.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.led_controller import LEDThread


MAIN_PAGE = """<!doctype html>
<html>
<head>
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>LED Control</title>
<style>
body { font-family: sans-serif; text-align: center; margin-top: 2em; }
button { width: 80%; padding: 1em; font-size: 1.5em; margin: 1em 0; }
</style>
</head>
<body>
<h1>LED Test</h1>
<form action=\"/start\" method=\"get\"><button type=\"submit\">Start</button></form>
<form action=\"/stop\"  method=\"get\"><button type=\"submit\">Stop</button></form>
</body>
</html>"""


class _Handler(BaseHTTPRequestHandler):
    """Handle requests for the LED control page."""

    # The HTTPServer instance will attach ``led_thread`` attribute at runtime.

    def do_GET(self) -> None:  # pragma: no cover - trivial routing
        if self.path == "/start":
            self.server.led_thread.start_test()  # type: ignore[attr-defined]
            self._redirect("/")
        elif self.path == "/stop":
            self.server.led_thread.stop_test()  # type: ignore[attr-defined]
            self._redirect("/")
        elif self.path == "/":
            self._send_html(MAIN_PAGE)
        else:
            self.send_error(404, "Not found")

    # ------------------------------------------------------------------
    def log_message(self, format: str, *args: object) -> None:
        """Silence default logging to keep console tidy."""

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
    """Background thread running a small HTTP server.

    Parameters
    ----------
    stop_evt:
        Event used to signal shutdown.
    led_thread:
        Instance of :class:`LEDThread` whose pattern will be controlled.
    host, port:
        Address where the server should listen.  Defaults to ``0.0.0.0:8000`` so
        it can be reached from other devices on the LAN.
    """

    def __init__(self, stop_evt: threading.Event, led_thread: LEDThread, host: str = "0.0.0.0", port: int = 8000) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.led_thread = led_thread
        self.host = host
        self.port = port
        self.httpd: HTTPServer = HTTPServer((host, port), _Handler)
        # expose LED thread to handler via server attribute
        self.httpd.led_thread = led_thread  # type: ignore[attr-defined]
        self.httpd.timeout = 0.5  # so serve loop can check stop event

    def run(self) -> None:  # pragma: no cover - contains blocking loop
        print(f"[Web] server listening on {self.host}:{self.port}")
        while not self.stop_evt.is_set():
            self.httpd.handle_request()
        self.httpd.server_close()
        print("[Web] server stopped")
