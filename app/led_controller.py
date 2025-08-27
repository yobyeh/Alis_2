"""app/led_controller.py

Threaded controller for a 16x16 WS2812B LED matrix.
Cycles through red, green, and blue test pattern.
"""

import logging
import threading
import time

try:  # Try to import the real hardware library
    from rpi_ws281x import PixelStrip, Color
except Exception:  # pragma: no cover - hardware not present
    PixelStrip = None  # type: ignore
    def Color(r, g, b):  # type: ignore
        return (r, g, b)
    logging.warning("rpi_ws281x not available; LED controller will be a no-op")


class LEDThread(threading.Thread):
    """Simple LED controller thread.

    Displays a solid color over the entire 16x16 matrix and rotates
    through red, green and blue until the stop event is set.
    Brightness is read from settings on each cycle if the hardware
    library supports it.
    """

    def __init__(
        self,
        stop_evt: threading.Event,
        get_settings,
        count: int = 16 * 16,
        pin: int = 13,
        channel: int | None = None,
    ):
        """
        Args:
            stop_evt: Event used to signal shutdown.
            get_settings: Callable returning the settings dict.
            count: Number of pixels in the matrix.
            pin: GPIO pin used for the data line (BCM numbering).
            channel: PWM channel for ``rpi_ws281x``. If ``None`` an appropriate
                channel is chosen based on the pin (pins 13/19/41/45/53 -> 1
                otherwise 0).
        """

        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.get_settings = get_settings
        self.count = count
        self.pin = pin
        self.strip = None

        if PixelStrip:
            try:
                brightness = int(get_settings().get("led", {}).get("brightness", 64))
            except Exception:
                brightness = 64

            if channel is None:
                channel = 1 if pin in (13, 19, 41, 45, 53) else 0

            self.strip = PixelStrip(count, pin, brightness=brightness, channel=channel)
            self.strip.begin()

    def _set_all(self, color):
        if not self.strip:
            return
        for i in range(self.count):
            self.strip.setPixelColor(i, color)
        self.strip.show()

    def run(self):
        if not self.strip:
            # Hardware not available, just idle until stop
            while not self.stop_evt.is_set():
                time.sleep(0.5)
            return

        colors = [Color(255, 0, 0), Color(0, 255, 0), Color(0, 0, 255)]
        idx = 0
        while not self.stop_evt.is_set():
            settings = self.get_settings()
            try:
                brightness = int(settings.get("led", {}).get("brightness", 64))
                self.strip.setBrightness(brightness)
            except Exception:
                pass
            self._set_all(colors[idx % 3])
            idx += 1
            time.sleep(0.5)

        # Clear on exit
        self._set_all(Color(0, 0, 0))
