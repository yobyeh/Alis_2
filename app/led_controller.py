"""Threaded controller for a WS2812B LED matrix using the pi5neo library."""

import logging
import threading
import time
from typing import Callable

try:  # Try to import real hardware library
    from pi5neo import Pi5Neo
except Exception:  # pragma: no cover - hardware not present
    Pi5Neo = None  # type: ignore
    logging.warning("pi5neo not available; LED controller will be a no-op")


def Color(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Return an RGB tuple used by tests."""
    return (r, g, b)


class LEDThread(threading.Thread):
    """Progressively fills the LED strip with a solid color.

    Uses ``pi5neo`` to drive the LEDs.  When the strip cannot be initialised
    (e.g. on non-Raspberry Pi test systems) the thread idles until ``stop_evt``
    is set.
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        get_settings: Callable[[], dict],
        count: int = 16 * 16,
        device: str = "/dev/spidev1.0",
        freq_hz: int = 800,
    ) -> None:
        """Create the thread.

        Args:
            stop_evt: Event used to signal shutdown.
            get_settings: Callable returning the settings dict.
            count: Number of pixels in the matrix.
            device: SPI device path used by ``pi5neo``.
            freq_hz: SPI clock frequency.
        """
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.get_settings = get_settings
        self.count = count
        self.strip = None

        if Pi5Neo:
            try:
                self.strip = Pi5Neo(device, count, freq_hz)
                self.strip.clear_strip()
                self.strip.update_strip()
            except Exception:
                self.strip = None
                logging.warning("Failed to initialise Pi5Neo strip; LED controller will be idle")

        # Default colour/behaviour similar to original test script
        try:
            brightness = int(get_settings().get("led", {}).get("brightness", 40))
        except Exception:
            brightness = 40
        self.color = Color(0, brightness, 0)
        self.step_delay = 0.02  # seconds between lighting each pixel
        self.hold_delay = 2.0   # hold full strip on for this many seconds

    def _set_all(self, color: tuple[int, int, int]) -> None:
        """Set the entire strip to one colour and update it."""
        if not self.strip:
            return
        for i in range(self.count):
            self.strip.set_led_color(i, *color)
        self.strip.update_strip()

    def run(self) -> None:
        if not self.strip:
            # Hardware not available, just idle until stop
            while not self.stop_evt.is_set():
                time.sleep(0.5)
            return

        try:
            for i in range(self.count):
                if self.stop_evt.is_set():
                    break
                self.strip.set_led_color(i, *self.color)
                self.strip.update_strip()
                time.sleep(self.step_delay)
            if not self.stop_evt.is_set():
                time.sleep(self.hold_delay)
        finally:
            self.strip.clear_strip()
            self.strip.update_strip()
