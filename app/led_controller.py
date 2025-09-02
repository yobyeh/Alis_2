# app/led_controller.py
# LED controller using SPI-based NeoPixel strip

import logging
import threading
import time
from typing import Callable, Optional, Tuple

try:
    import board
    import busio
    import neopixel
except Exception:
    board = busio = neopixel = None  # type: ignore[assignment]
    logging.warning("neopixel libraries not available; LED controller will be a no-op")

Color = Tuple[int, int, int]


class LEDThread(threading.Thread):
    """Background worker driving the LED strip.

    The thread idles until a pattern is selected via :meth:`set_pattern`.
    Currently supported patterns:

    ``rgb_cycle`` – cycle through red, green and blue.
    ``off``       – turn all LEDs off.
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        get_settings: Callable[[], dict],
        led_count: int = 256,
        baudrate: int = 1_600_000,
        brightness: float = 0.20,
        hold_sec: float = 1.0,
    ) -> None:
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.get_settings = get_settings
        self.led_count = led_count
        self.hold_sec = hold_sec
        self._pattern = "off"
        self._pattern_lock = threading.Lock()
        self.px: Optional[neopixel.NeoPixel] = None  # type: ignore[type-arg]

        if board and busio and neopixel:
            try:
                spi = busio.SPI(board.D21, MOSI=board.D20)
                while not spi.try_lock():
                    pass
                spi.configure(baudrate=baudrate, phase=0, polarity=0)
                spi.unlock()
                self.px = neopixel.NeoPixel_SPI(
                    spi,
                    self.led_count,
                    pixel_order=neopixel.GRB,
                    brightness=brightness,
                    auto_write=False,
                )
            except Exception as exc:  # pragma: no cover - hardware dependent
                logging.warning(f"Failed to init neopixel SPI: {exc}")
                self.px = None
        else:  # pragma: no cover - hardware dependent
            logging.warning("neopixel or board libraries unavailable; LED thread will idle")

    # ------------------- public API -------------------
    def set_pattern(self, name: str) -> None:
        """Select a pattern for the thread to run."""
        with self._pattern_lock:
            self._pattern = name

    # ------------------ internal helpers ------------------
    def _current_pattern(self) -> str:
        with self._pattern_lock:
            return self._pattern

    def _update_brightness(self) -> None:
        if not self.px:
            return
        try:
            b = int(self.get_settings().get("led", {}).get("brightness", 20))
            self.px.brightness = max(0.0, min(1.0, b / 255.0))
        except Exception:
            pass

    def _set_all(self, color: Color) -> None:
        if not self.px:
            return
        self._update_brightness()
        self.px.fill(color)
        self.px.show()

    # -------------------- thread loop --------------------
    def run(self) -> None:  # pragma: no cover - contains time-based loop
        if not self.px:
            # Hardware not present — idle until asked to stop
            while not self.stop_evt.is_set():
                time.sleep(0.5)
            return

        try:
            while not self.stop_evt.is_set():
                pattern = self._current_pattern()
                if pattern == "rgb_cycle":
                    for name, col in (
                        ("RED", (25, 0, 0)),
                        ("GREEN", (0, 25, 0)),
                        ("BLUE", (0, 0, 25)),
                    ):
                        if self.stop_evt.is_set() or self._current_pattern() != "rgb_cycle":
                            break
                        print(f"[LED] {name}")
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
        finally:
            try:
                self._set_all((0, 0, 0))
            except Exception:
                pass
