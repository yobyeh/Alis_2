# app/led_controller.py
# Minimal LED controller thread:
# - Consumes frames from a multiprocessing.Queue
# - Each item is either:
#       bytes (GRB triplets for all pixels)
#       or (bytes, Optional[int]) to override brightness per frame
# - Sends frames to Teensy using a tiny header
# - Exits cleanly when SENTINEL (None) is received
#
# In main/shutdown, enqueue the sentinel to unblock and stop:
#   frame_queue.put_nowait(SENTINEL)  # SENTINEL == None

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Tuple, Any, Union

try:
    import serial
    from serial.tools import list_ports
except Exception:
    serial = None  # type: ignore
    list_ports = None  # type: ignore

# ---------------- Types & Sentinel ----------------
FramePayload = bytes
FrameItem = Union[FramePayload, Tuple[FramePayload, Optional[int]], None]
SENTINEL = None  # safe, picklable for multiprocessing.Queue

Color = Tuple[int, int, int]


# ---------------- Utilities ----------------
def find_teensy(default: str = "/dev/ttyACM0") -> str:
    """Return the serial port of a connected Teensy, or fallback to default."""
    if not list_ports:
        return default
    for p in list_ports.comports():
        desc = f"{p.description or ''} {p.manufacturer or ''}"
        if "Teensy" in desc or "Teensyduino" in desc:
            return p.device
    return default


def _clamp_byte(x: int) -> int:
    return 0 if x < 0 else 255 if x > 255 else x


def _send_frame(ser: Any, payload_grb: bytes, brightness: int) -> None:
    """Send a single frame to the Teensy using a minimal header."""
    num_pixels = len(payload_grb) // 3
    brightness = _clamp_byte(brightness)
    # Header: 0xAB 0xCD 0xF1 0x00 [num_lo] [num_hi] [brightness]
    hdr = bytes((0xAB, 0xCD, 0xF1, 0x00, num_pixels & 0xFF, (num_pixels >> 8) & 0xFF, brightness))
    ser.write(hdr)
    ser.write(payload_grb)
    ser.flush()


# ---------------- Thread ----------------
class LEDController(threading.Thread):
    """
    Minimal LED controller thread.

    Args:
        stop_evt: threading.Event used to request shutdown.
        frame_queue: multiprocessing.Queue[FrameItem] — frames to display or SENTINEL to stop.
        current_settings: shared dict containing runtime settings (e.g., {'led': {'brightness': 128}})
        settings_lock: lock guarding access to current_settings
        port: optional serial port; auto-detects Teensy if not given
        baud: serial baud rate (default 2_000_000)

    Behavior:
        - Blocks briefly on frame_queue.get(timeout=...) to pull frames.
        - If it receives SENTINEL (None), exits cleanly.
        - Uses per-frame brightness if provided; otherwise reads from current_settings.
    """

    def __init__(
        self,
        *,
        stop_evt: threading.Event,
        frame_queue,                   # multiprocessing.Queue[FrameItem]
        current_settings: dict,
        settings_lock: threading.Lock,
        port: Optional[str] = None,
        baud: int = 2_000_000,
    ) -> None:
        super().__init__(name="LEDControllerThread", daemon=False)
        self.stop_evt = stop_evt
        self.frame_queue = frame_queue
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        self.port = port or find_teensy()
        self.baud = baud
        self.ser: Optional["serial.Serial"] = None

        # --- SETTINGS CHECK (add your validation here) -----------------------
        # Example (uncomment & customize as needed):
        # with self.settings_lock:
        #     led_cfg = self.current_settings.get("led", {})
        #     # Validate brightness (0-255)
        #     default_brightness = int(led_cfg.get("brightness", 128))
        #     self.default_brightness = _clamp_byte(default_brightness)
        #     # Optionally validate matrix size (if you track width/height in settings)
        #     # self.width = int(led_cfg.get("width", 16))
        #     # self.height = int(led_cfg.get("height", 16))
        # --------------------------------------------------------------------

        if not hasattr(self, "default_brightness"):
            self.default_brightness = 128  # safe fallback

    # --------- internals ---------
    def _ensure_serial(self) -> Optional["serial.Serial"]:
        if self.ser:
            return self.ser
        if serial is None:
            logging.warning("pyserial not available; LEDController will idle.")
            return None
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.2, write_timeout=1.0)
            # Optional: read boot banner / wait briefly for RDY
            t0 = time.time()
            self.ser.reset_input_buffer()
            while time.time() - t0 < 2.0 and not self.stop_evt.is_set():
                try:
                    line = self.ser.readline().decode("utf-8", "ignore").strip()
                    if line:
                        logging.info("Teensy: %s", line)
                        if line == "RDY":
                            break
                except Exception:
                    break
        except Exception as e:
            logging.warning("Failed to open serial port %s: %s", self.port, e)
            self.ser = None
        return self.ser

    def _close_serial(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def _current_brightness(self) -> int:
        try:
            with self.settings_lock:
                b = int(self.current_settings.get("LED Brightness", self.default_brightness))
        except Exception as e:
            print("default brightness due to exception:", e)
            b = self.default_brightness
        print(f"[LEDController] Using brightness: {b}")
        return _clamp_byte(b)

    # --------- main loop ---------
    def run(self) -> None:
        logging.info("[LED] controller starting on %s", self.port)
        ser = self._ensure_serial()
        if not ser:
            # Idle if we cannot open serial; still allow graceful shutdown.
            while not self.stop_evt.is_set():
                time.sleep(0.2)
            return

        try:
            while not self.stop_evt.is_set():
                # Try to get the next frame (or sentinel) with a short timeout
                try:
                    item: FrameItem = self.frame_queue.get(timeout=0.02)
                except Exception:
                    # No frame yet — light sleep to reduce CPU, adjust if targeting FPS
                    time.sleep(0.05)
                    continue

                # --- Sentinel to exit cleanly --- #this may need to go, main sends this 
                if item is SENTINEL:
                    break

                # Normalize to (payload, brightness_override)
                if isinstance(item, (bytes, bytearray, memoryview)):
                    payload: bytes = bytes(item)
                    br_override: Optional[int] = None
                else:
                    payload, br_override = item  # type: ignore[assignment]
                    payload = bytes(payload)

                if br_override is not None:
                    print(f"[LEDController] Using per-frame brightness override: {br_override}")
                    brightness = _clamp_byte(int(br_override))
                else:
                    print("[LEDController] Using _current_brightness()")
                    brightness = self._current_brightness()

                print(f"[LEDController] Sending frame with brightness: {brightness}")
                try:
                    _send_frame(ser, payload, brightness)
                except Exception as e:
                    # Quick reconnect attempt, then continue
                    logging.warning("Serial write failed: %s (attempting reconnect)", e)
                    self._close_serial()
                    if self.stop_evt.is_set():
                        break
                    time.sleep(0.2)
                    ser = self._ensure_serial()
                    if ser:
                        try:
                            _send_frame(ser, payload, brightness)
                        except Exception as e2:
                            logging.error("Serial write failed after reconnect: %s", e2)
        finally:
            blank_payload = bytes([0, 0, 0]) * (256)  # adjust pixel count as needed
            _send_frame(self.ser, blank_payload, 0)   # brightness 0 or your preferred value
            self._close_serial()
            logging.info("[LED] controller stopped")