from __future__ import annotations

import json
import threading
import time
from typing import Callable, List, Set, Tuple, Optional

try:  # pragma: no cover - serial may not be installed
    import serial
except Exception:  # pragma: no cover
    serial = None  # type: ignore[assignment]

from app.led_controller import find_teensy, send_frame

Color = Tuple[int, int, int]


class AnimationControllerThread(threading.Thread):
    """Thread driving frames to LEDs and web clients.

    The thread maintains an internal framebuffer and periodically pushes it to
    the LED controller and any registered websocket clients.  Flags allow
    runtime control over whether frames are sent to either destination.

    Modes
    -----
    static:
        Framebuffer is sent as-is.
    animation:
        Simple RGB cycling animation.
    draw:
        Framebuffer receives updates from ``update_pixel`` calls, typically
        originating from a web drawing client.
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        width: int = 16,
        height: int = 16,
        port: Optional[str] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.width = width
        self.height = height
        self.port = port or find_teensy()
        self.ser: Optional[serial.Serial] = None

        self.mode = "static"
        self.send_to_led = True
        self.send_to_web = True

        self._frame: List[List[Color]] = [
            [(0, 0, 0) for _ in range(width)] for _ in range(height)
        ]
        self._frame_lock = threading.Lock()

        # Web clients register a callable used to send JSON payloads
        self._web_clients: Set[Callable[[str], None]] = set()

    # ------------------------------------------------------------------
    # Public API
    def set_mode(self, mode: str) -> None:
        """Set operating mode: ``static``, ``animation`` or ``draw``."""

        if mode in {"static", "animation", "draw"}:
            self.mode = mode

    def register_client(self, sender: Callable[[str], None]) -> None:
        """Register a callable used to send messages to a websocket client."""

        self._web_clients.add(sender)

    def unregister_client(self, sender: Callable[[str], None]) -> None:
        self._web_clients.discard(sender)

    def update_pixel(self, x: int, y: int, color: Color) -> None:
        """Update a single pixel in the framebuffer."""

        with self._frame_lock:
            if 0 <= x < self.width and 0 <= y < self.height:
                self._frame[y][x] = color

    # ------------------------------------------------------------------
    # Internal helpers
    def _ensure_serial(self) -> Optional[serial.Serial]:
        if self.ser:
            return self.ser
        if serial is None:  # pragma: no cover - serial missing
            return None
        try:
            self.ser = serial.Serial(self.port, 2_000_000, timeout=0.2)
        except Exception:  # pragma: no cover - hardware specific
            self.ser = None
        return self.ser

    def _frame_bytes(self) -> bytes:
        with self._frame_lock:
            data = []
            for row in self._frame:
                for r, g, b in row:
                    data.extend([g & 0xFF, r & 0xFF, b & 0xFF])
            return bytes(data)

    def _broadcast(self) -> None:
        if not self.send_to_web:
            return
        with self._frame_lock:
            payload = json.dumps({"frame": self._frame})
        for sender in list(self._web_clients):
            try:
                sender(payload)
            except Exception:
                self._web_clients.discard(sender)

    def _animate(self, t: float) -> None:
        """Very small demo animation cycling primary colors."""

        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        idx = int(t) % len(colors)
        col = colors[idx]
        with self._frame_lock:
            for y in range(self.height):
                for x in range(self.width):
                    self._frame[y][x] = col

    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - contains time loop
        print("[Anim] controller starting")
        while not self.stop_evt.is_set():
            now = time.time()
            if self.mode == "animation":
                self._animate(now)
            # static and draw modes rely on external updates

            payload = self._frame_bytes()
            if self.send_to_led:
                ser = self._ensure_serial()
                if ser:
                    try:
                        send_frame(ser, payload, brightness=30)
                    except Exception:
                        pass
            self._broadcast()
            time.sleep(0.1)
        print("[Anim] controller stopped")
