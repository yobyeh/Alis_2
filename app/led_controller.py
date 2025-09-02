# app/led_simple.py
# Super simple WS2812B loop using pi5neo:
# - Lights ALL LEDs to RED, then GREEN, then BLUE
# - Prints the color name when shown
# - Updates the whole strip at once (no per-pixel stepping) to avoid flicker

import logging
import threading
import time
from typing import Callable, Tuple

try:
    from pi5neo import Pi5Neo
except Exception:
    Pi5Neo = None
    logging.warning("pi5neo not available; LED controller will be a no-op")

Color = Tuple[int, int, int]

# If your LEDs expect GRB order instead of RGB, set ORDER = (1, 0, 2)
ORDER = (0, 1, 2)  # (R, G, B) index order; change to (1,0,2) for GRB strips

def _apply_order(c: Color) -> Color:
    return (c[ORDER[0]], c[ORDER[1]], c[ORDER[2]])

class LEDThread(threading.Thread):
    """
    Minimal LED worker:
      - Initializes strip
      - Loops over solid RED -> GREEN -> BLUE
      - Holds each color for hold_sec
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        get_settings: Callable[[], dict],
        count: int = 16 * 16,
        device: str = "/dev/spidev1.0",
        freq_hz: int = 800,
        hold_sec: float = 1.0,
    ):
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.get_settings = get_settings
        self.count = int(count)
        self.hold_sec = float(hold_sec)

        self.strip = None
        if Pi5Neo:
            try:
                self.strip = Pi5Neo(device, self.count, freq_hz)
                self.strip.clear_strip()
                self.strip.update_strip()
            except Exception as e:
                logging.warning(f"Failed to init Pi5Neo: {e}")
                self.strip = None
        else:
            logging.warning("Pi5Neo unavailable; LED thread will idle")

    def _brightness_scaled(self, base: Color) -> Color:
        try:
            b = int(self.get_settings().get("led", {}).get("brightness", 20))
        except Exception:
            b = 20
        # Expecting 0..255 scale
        # Scale unit colors (1,0,0) by b to (b,0,0) etc.
        return tuple(int((v > 0) * b) for v in base)  # type: ignore[return-value]

    def _set_all(self, color: Color) -> None:
        if not self.strip:
            return
        r, g, b = _apply_order(color)
        for i in range(self.count):
            self.strip.set_led_color(i, r, g, b)
        self.strip.update_strip()

    def run(self) -> None:
        if not self.strip:
            # Hardware not present — idle until asked to stop
            while not self.stop_evt.is_set():
                time.sleep(0.5)
            return

        try:
            # Solid color cycle
            while not self.stop_evt.is_set():
                for name, base in (("RED", (1, 0, 0)), ("GREEN", (0, 1, 0)), ("BLUE", (0, 0, 1))):
                    if self.stop_evt.is_set():
                        break
                    color = self._brightness_scaled(base)
                    print(f"[LED] Showing {name} (RGB={color})")
                    self._set_all(color)

                    # Sleep in small chunks so we can react to stop_evt promptly
                    t0 = time.time()
                    while not self.stop_evt.is_set() and (time.time() - t0) < self.hold_sec:
                        time.sleep(0.05)
        finally:
            try:
                if self.strip:
                    self.strip.clear_strip()
                    self.strip.update_strip()
            except Exception:
                pass
