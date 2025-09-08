# app/led_controller.py
# LED controller using a Teensy board over serial

"""Threaded driver for the LED matrix.

This module talks to a Teensy based LED controller over a serial
connection.  The protocol matches the small standalone script used by the
project for manual testing.  The thread exposes a :class:`LEDThread` class
which allows selecting simple patterns such as ``rgb_cycle`` or ``off``.

The implementation intentionally keeps hardware specific code small so
that unit tests can provide a dummy serial object.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Optional, Tuple

try:  # pragma: no cover - serial may not be installed in test env
    import serial
    from serial.tools import list_ports
except Exception:  # pragma: no cover - serial fallback
    serial = None  # type: ignore[assignment]
    list_ports = None  # type: ignore[assignment]


Color = Tuple[int, int, int]


# ---------------------------------------------------------------------------
# Helper functions mirroring the standalone script

def find_teensy(default: str = "/dev/ttyACM0") -> str:
    """Return the serial port of a connected Teensy if available."""

    if not list_ports:  # pragma: no cover - only when pyserial missing
        return default
    for p in list_ports.comports():
        desc = (p.description or "") + " " + (p.manufacturer or "")
        if "Teensy" in desc or "Teensyduino" in desc:
            return p.device
    return default


def build_solid_grb(w: int, h: int, su: int, rgb: Color) -> bytes:
    """Return a GRB payload filling the whole panel with ``rgb``."""

    r, g, b = rgb
    trip = bytes((g & 0xFF, r & 0xFF, b & 0xFF))  # GRB order
    return trip * (w * h * su)


def send_frame(ser: Any, payload_grb: bytes, brightness: int) -> None:
    """Send a frame payload to ``ser`` using the Teensy framing protocol."""

    num = len(payload_grb) // 3
    hdr = bytes(
        (0xAB, 0xCD, 0xF1, 0x00, num & 0xFF, (num >> 8) & 0xFF, brightness & 0xFF)
    )
    ser.write(hdr + payload_grb)
    ser.flush()
    ser.timeout = 2
    # read optional acknowledgement line
    try:
        line = ser.readline().decode("utf-8", "ignore").strip()
        if line:
            logging.info("Teensy: %s", line)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Thread implementation


class LEDThread(threading.Thread):
    """Background worker driving the LED strip via a Teensy controller."""

    def __init__(
        self,
        stop_evt: threading.Event,
        get_settings: Callable[[], dict],
        width: int = 16,
        height: int = 16,
        strips_used: int = 1,
        brightness: int = 30,
        hold_sec: float = 1.0,
        port: Optional[str] = None,
        ser: Optional[serial.Serial] = None,
    ) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.get_settings = get_settings
        self.width = width
        self.height = height
        self.strips_used = strips_used
        self.default_brightness = brightness
        self.hold_sec = hold_sec
        self._pattern = "off"
        self._pattern_lock = threading.Lock()

        self.port = port or find_teensy()
        self.ser: Optional[serial.Serial] = ser

        # NEW: serialize writes to the Teensy
        self._io_lock = threading.Lock()

    # ------------------- public API -------------------
    def set_pattern(self, name: str) -> None:
        """Select a pattern for the thread to run."""
        with self._pattern_lock:
            self._pattern = name
        # If we were asked to turn off immediately, clear LEDs now.
        if name == "off":
            self._clear_immediate()

    def start_test(self) -> None:
        """Convenience wrapper to start the RGB test pattern."""
        self.set_pattern("rgb_cycle")

    def stop_test(self) -> None:
        """Stop any active test pattern and turn LEDs off."""
        self.set_pattern("off")  # set + immediate clear via set_pattern

    def send_raw_frame(self, payload_grb: bytes, brightness: Optional[int] = None) -> None:
        """Send a pre-built GRB payload to the LEDs."""
        ser = self._ensure_serial()
        if not ser:
            return
        with self._io_lock:
            send_frame(ser, payload_grb, brightness if brightness is not None else self._get_brightness())

    # ------------------ internal helpers ------------------
    def _current_pattern(self) -> str:
        with self._pattern_lock:
            return self._pattern

    def _ensure_serial(self) -> Optional[serial.Serial]:
        if self.ser:
            return self.ser
        if serial is None:  # pragma: no cover - serial missing
            logging.warning("pyserial not available; LED thread will idle")
            self.ser = None
            return None
        try:
            self.ser = serial.Serial(self.port, 2_000_000, timeout=0.2)
        except Exception as exc:  # pragma: no cover - hardware dependent
            logging.warning("Failed to open serial port %s: %s", self.port, exc)
            self.ser = None
        return self.ser

    def _close_serial(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _get_brightness(self) -> int:
        try:
            return int(self.get_settings().get("led", {}).get("brightness", self.default_brightness))
        except Exception:
            return self.default_brightness

    def _set_all(self, color: Color) -> None:
        ser = self._ensure_serial()
        if not ser:
            return
        payload = build_solid_grb(self.width, self.height, self.strips_used, color)
        with self._io_lock:
            send_frame(ser, payload, self._get_brightness())

    def _clear_immediate(self) -> None:
        """Immediately clear LEDs to black (thread-safe)."""
        try:
            self._set_all((0, 0, 0))
        except Exception:
            pass

    # -------------------- thread loop --------------------
    def run(self) -> None:  # pragma: no cover - contains time-based loop
        print("[LED] thread starting up")
        ser = self._ensure_serial()
        if not ser:
            while not self.stop_evt.is_set():
                time.sleep(0.5)
            return

        # Flush stale boot text and wait up to 5s for RDY once
        ser.reset_input_buffer()
        t0 = time.time()
        while time.time() - t0 < 5.0 and not self.stop_evt.is_set():
            line = ser.readline().decode("utf-8", "ignore").strip()
            if line:
                logging.info("Teensy: %s", line)
                if line == "RDY":
                    break

        last_pattern: Optional[str] = None

        try:
            while not self.stop_evt.is_set():
                pattern = self._current_pattern()

                # NEW: clear on transition *away* from rgb_cycle
                if last_pattern == "rgb_cycle" and pattern != "rgb_cycle":
                    self._clear_immediate()

                if pattern == "rgb_cycle":
                    for name, col in (
                        ("RED", (25, 0, 0)),
                        ("GREEN", (0, 25, 0)),
                        ("BLUE", (0, 0, 25)),
                    ):
                        if self.stop_evt.is_set() or self._current_pattern() != "rgb_cycle":
                            break
                        logging.debug("[LED] %s", name)
                        self._set_all(col)
                        t0 = time.time()
                        while (
                            not self.stop_evt.is_set()
                            and self._current_pattern() == "rgb_cycle"
                            and (time.time() - t0) < self.hold_sec
                        ):
                            time.sleep(0.05)
                else:
                    time.sleep(0.1)

                last_pattern = pattern
        finally:
            # Always leave LEDs off when the thread exits
            try:
                self._clear_immediate()
            except Exception:
                pass
            self._close_serial()
