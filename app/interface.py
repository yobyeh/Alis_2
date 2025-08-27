# app/interface.py
# Alis — interface threads:
#   - DisplayThread: owns LCD, renders status + data-driven menu
#   - ButtonsThread: translates GPIO presses into controller events
#
# Notes:
# - Rotation is read ONCE at startup (passed in from main.py).
# - Brightness/sleep/screensaver read from settings on the fly.
# - Expects:
#     * MenuController (controller) with .view() and .last_input_ts
#     * StatusProvider (status_provider) with .snapshot()
#     * get_theme(): dict with fg/bg/accent
#     * get_settings(): dict-like settings
#
# Wiring (BCM):
#   UP -> GPIO17, DOWN -> GPIO22, SELECT -> GPIO23, BACK -> GPIO24
#
# Requires:
#   - driver/LCD_2inch.py (Waveshare)
#   - gpiozero + lgpio backend (GPIOZERO_PIN_FACTORY=lgpio)

import time
import threading
import logging
from typing import Dict, Any, Callable
from PIL import Image
import PIL.Image as PILImage
from driver import LCD_2inch
from gpiozero import Button

from app.ui_render import render_menu

# Button pins (BCM numbering)
BTN_PINS = {"UP": 17, "DOWN": 22, "SELECT": 23, "BACK": 24}
DEBOUNCE_S = 0.05
RENDER_INTERVAL = 0.15  # seconds

def _orient(img: PILImage.Image, rotation: int) -> PILImage.Image:
    """Rotate image clockwise by rotation (0/90/180/270)."""
    if rotation == 0:   return img
    if rotation == 90:  return img.transpose(PILImage.Transpose.ROTATE_270)  # CW
    if rotation == 180: return img.transpose(PILImage.Transpose.ROTATE_180)
    if rotation == 270: return img.transpose(PILImage.Transpose.ROTATE_90)   # CW
    return img


class DisplayThread(threading.Thread):
    """
    Owns the LCD and rendering.
    Reads rotation once at startup (no hot-apply).
    Continuously applies brightness and sleep/screensaver logic from settings.
    """
    def __init__(
        self,
        stop_evt: threading.Event,
        controller,                      # MenuController
        status_provider,                 # StatusProvider
        get_theme: Callable[[], Dict[str, str]],
        get_settings: Callable[[], Dict[str, Any]],
        assets_dir: str = "assets",
        rotation: int = 0,               # read from settings in main.py
    ):
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.controller = controller
        self.status = status_provider
        self.get_theme = get_theme
        self.get_settings = get_settings
        self.assets_dir = assets_dir

        self._rot = int(rotation) % 360

        # Init display
        self.disp = LCD_2inch.LCD_2inch()
        self.disp.Init()

        # Panel physical size
        self.panel_w, self.panel_h = self.disp.width, self.disp.height

        # Logical canvas based on startup rotation (upright coords)
        if self._rot in (90, 270):
            self.W, self.H = self.panel_h, self.panel_w
        else:
            self.W, self.H = self.panel_w, self.panel_h

        self.canvas = Image.new("RGB", (self.W, self.H), "black")
        self._last_render = 0.0

        # Apply initial brightness and show splash
        self._apply_brightness(self.get_settings().get("display", {}).get("brightness", 100))
        self._show_splash_once()

    # -------- helpers --------
    def _apply_brightness(self, val: int):
        """Map 0..100 to driver backlight if available; fallback on/off."""
        try:
            val = int(val)
        except (ValueError, TypeError):
            logging.warning("Invalid brightness value %r; defaulting to 100", val)
            val = 100
        val = max(0, min(100, val))
        try:
            # Many Waveshare drivers accept 0..100 for duty
            self.disp.bl_DutyCycle(val)
        except AttributeError:
            try:
                if val <= 0 and hasattr(self.disp, "bl_Off"):
                    self.disp.bl_Off()
                elif val > 0 and hasattr(self.disp, "bl_On"):
                    self.disp.bl_On()
            except Exception:
                pass

    def _show_splash_once(self):
        try:
            from PIL import Image
            splash = Image.open(f"{self.assets_dir}/splash.png").convert("RGB")
            splash = splash.resize((self.W, self.H))
            self.disp.ShowImage(_orient(splash, self._rot))
            time.sleep(1.2)
        except Exception:
            pass  # no splash available, or load failed — ignore

    def _sleeping(self, idle_s: float, settings: Dict[str, Any]) -> bool:
        sleep_after = max(0, int(settings.get("display", {}).get("sleep_seconds", 0)))
        return sleep_after > 0 and idle_s >= sleep_after

    def _screensaver(self, idle_s: float, settings: Dict[str, Any]) -> bool:
        disp = settings.get("display", {})
        if not disp.get("screensaver_enabled", False):
            return False
        sleep_after = max(0, int(disp.get("sleep_seconds", 0)))
        if sleep_after <= 20:
            return False
        # Start screensaver shortly before sleeping
        return idle_s >= (sleep_after - 10)

    def _render_screensaver(self):
        # Simple standby frame
        from PIL import ImageDraw
        from app.ui_render import load_font
        d = ImageDraw.Draw(self.canvas)
        d.rectangle((0, 0, self.W, self.H), fill="black")
        msg = "Screensaver"
        f = load_font(22)
        tw = d.textlength(msg, font=f)
        d.text(((self.W - tw) // 2, self.H // 2 - 12), msg, fill="gray", font=f)
        self.disp.ShowImage(_orient(self.canvas, self._rot))

    # -------- thread run loop --------
    def run(self):
        try:
            while not self.stop_evt.is_set():
                settings = self.get_settings()
                theme = self.get_theme()

                # apply brightness if changed
                self._apply_brightness(settings.get("display", {}).get("brightness", 100))

                # idle time since last input
                idle = time.time() - self.controller.last_input_ts

                # sleeping?
                if self._sleeping(idle, settings):
                    # turn off backlight and idle; any button will update last_input_ts and wake us
                    self._apply_brightness(0)
                    time.sleep(0.2)
                    continue

                # screensaver?
                if self._screensaver(idle, settings):
                    # dim a bit during saver
                    target = max(5, int(settings.get("display", {}).get("brightness", 100)) // 4)
                    self._apply_brightness(target)
                    self._render_screensaver()
                    time.sleep(0.05)
                    continue

                # normal render throttled
                now = time.time()
                if now - self._last_render >= RENDER_INTERVAL:
                    view = self.controller.view()
                    status = self.status.snapshot()
                    render_menu(self.canvas, view, status, theme)
                    self.disp.ShowImage(_orient(self.canvas, self._rot))
                    self._last_render = now

                time.sleep(0.02)
        finally:
            # clear screen and backlight off
            try:
                self.canvas.paste((0, 0, 0), (0, 0, self.W, self.H))
                self.disp.ShowImage(_orient(self.canvas, self._rot))
            except Exception:
                pass
            self._apply_brightness(0)
            try:
                self.disp.module_exit()
            except Exception:
                pass


class ButtonsThread(threading.Thread):
    """Owns GPIO buttons, translates them to controller events."""
    def __init__(self, stop_evt: threading.Event, controller):
        super().__init__(daemon=True)
        self.stop_evt = stop_evt
        self.controller = controller
        self.buttons = []

    def _fire(self, ev: str):
        # Update controller (which updates last_input_ts)
        self.controller.on_event(ev)

    def run(self):
        try:
            mapping = {
                "UP":     lambda: self._fire("UP"),
                "DOWN":   lambda: self._fire("DOWN"),
                "SELECT": lambda: self._fire("SELECT"),
                "BACK":   lambda: self._fire("BACK"),
            }
            for name, pin in BTN_PINS.items():
                b = Button(pin, pull_up=True, bounce_time=DEBOUNCE_S)
                b.when_pressed = mapping[name]
                self.buttons.append(b)

            while not self.stop_evt.is_set():
                time.sleep(0.05)
        finally:
            for b in self.buttons:
                try:
                    b.close()
                except Exception:
                    pass
