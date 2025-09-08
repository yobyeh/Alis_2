# app/animation_controller.py
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
    """Thread driving frames to LEDs and (optionally) web clients.

    Modes
    -----
    static:    Framebuffer is sent as-is.
    animation: Simple RGB cycling demo.
    draw:      External callers update pixels via update_pixel(...).
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        width: int = 16,
        height: int = 16,
        port: Optional[str] = None,
        brightness: int = 30,
        fps: float = 20.0,
    ) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.width = width
        self.height = height
        self.port = port or find_teensy()
        self.brightness = brightness
        self.fps = max(1.0, float(fps))

        self.ser: Optional[serial.Serial] = None
        self.mode = "static"         # "static" | "animation" | "draw"
        self.send_to_led = True      # can be toggled if you want preview-only
        self.send_to_web = True      # not used by the new web_server (it polls)

        # Framebuffer: row-major [y][x] as RGB tuples
        self._frame: List[List[Color]] = [
            [(0, 0, 0) for _ in range(width)] for _ in range(height)
        ]
        self._frame_lock = threading.Lock()

        # Optional: legacy push to self-registered web clients (JSON)
        self._web_clients: Set[Callable[[str], None]] = set()

        # A "dirty" event to allow immediate flushes (from WS)
        self._dirty_evt = threading.Event()

    # ------------------------------------------------------------------
    # Public API used by web_server.py
    def set_mode(self, mode: str) -> None:
        """Set operating mode: 'static', 'animation', or 'draw'."""
        if mode in {"static", "animation", "draw"}:
            self.mode = mode

    def register_client(self, sender: Callable[[str], None]) -> None:
        """Legacy JSON push registration (web_server now polls)."""
        self._web_clients.add(sender)

    def unregister_client(self, sender: Callable[[str], None]) -> None:
        self._web_clients.discard(sender)

    def update_pixel(self, x: int, y: int, color: Color) -> None:
        """Update a single pixel in the framebuffer."""
        if 0 <= x < self.width and 0 <= y < self.height:
            with self._frame_lock:
                self._frame[y][x] = (
                    int(color[0]) & 0xFF,
                    int(color[1]) & 0xFF,
                    int(color[2]) & 0xFF,
                )
        # mark dirty so the run loop can push sooner
        self._dirty_evt.set()

    def clear_panel(self) -> None:
        """Set all pixels to black and flush."""
        with self._frame_lock:
            for y in range(self.height):
                row = self._frame[y]
                for x in range(self.width):
                    row[x] = (0, 0, 0)
        self._dirty_evt.set()

    def flush(self) -> None:
        """Request that the current framebuffer be pushed ASAP."""
        self._dirty_evt.set()

    def framebuffer_rgb_bytes(self) -> tuple[bytes, int, int]:
        """Return (RGB bytes, width, height) for preview/broadcast.

        NOTE: This is **RGB** order for the web preview.
        Teensy output uses GRB (handled internally).
        """
        with self._frame_lock:
            out = bytearray(self.width * self.height * 3)
            i = 0
            for y in range(self.height):
                for x in range(self.width):
                    r, g, b = self._frame[y][x]
                    out[i] = r & 0xFF
                    out[i + 1] = g & 0xFF
                    out[i + 2] = b & 0xFF
                    i += 3
            return bytes(out), self.width, self.height

    # ------------------------------------------------------------------
    # Internal helpers
    def _ensure_serial(self) -> Optional[serial.Serial]:
        if self.ser:
            return self.ser
        if serial is None:  # pragma: no cover - pyserial missing
            return None
        try:
            self.ser = serial.Serial(self.port, 2_000_000, timeout=0.2)
        except Exception:
            self.ser = None
        return self.ser

    def _frame_bytes_grb(self) -> bytes:
        """Build GRB bytes for Teensy."""
        with self._frame_lock:
            data = bytearray(self.width * self.height * 3)
            i = 0
            for y in range(self.height):
                for x in range(self.width):
                    r, g, b = self._frame[y][x]
                    # Teensy expects GRB
                    data[i] = g & 0xFF
                    data[i + 1] = r & 0xFF
                    data[i + 2] = b & 0xFF
                    i += 3
            return bytes(data)

    def _broadcast_legacy_json(self) -> None:
        """Legacy push of the whole frame as JSON; optional."""
        if not self.send_to_web or not self._web_clients:
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
        col = colors[int(t) % 3]
        with self._frame_lock:
            for y in range(self.height):
                row = self._frame[y]
                for x in range(self.width):
                    row[x] = col

    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - contains time loop
        print("[Anim] controller starting")
        frame_period = 1.0 / self.fps
        next_tick = time.time()

        while not self.stop_evt.is_set():
            now = time.time()

            # Update animation if requested
            if self.mode == "animation":
                self._animate(now)

            # Push to LEDs if allowed or if explicitly flushed
            push_due = now >= next_tick or self._dirty_evt.is_set()
            if self.send_to_led and push_due:
                ser = self._ensure_serial()
                if ser:
                    try:
                        payload = self._frame_bytes_grb()
                        send_frame(ser, payload, brightness=self.brightness)
                    except Exception:
                        pass  # keep running if serial hiccups
                self._dirty_evt.clear()
                next_tick = now + frame_period

            # Optional legacy web push (the new web_server polls instead)
            # self._broadcast_legacy_json()

            # Small sleep to avoid busy loop; wake early on flush
            self._dirty_evt.wait(timeout=0.01)
            self._dirty_evt.clear()

        print("[Anim] controller stopped")
