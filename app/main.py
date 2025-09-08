# app/main.py
# Alis — main entrypoint
# - Loads menu.json + settings.json (with defaults + atomic save)
# - Creates MenuController (data-driven menu)
# - Starts DisplayThread (reads rotation ONCE at startup, honors brightness/sleep/screensaver)
# - Starts ButtonsThread (UP/DOWN/SELECT/BACK -> controller events)
# - Shows "restart required" indicator when a restart-only setting (e.g., rotation) changes
# - Starts WebServerThread (HTTP server for LED control)

import json
import os
import time
import threading
from typing import Dict, Any

from app.interface import DisplayThread, ButtonsThread
from app.menu_engine import MenuController
from app.status import StatusProvider
from app.storage import load_json, save_json_atomic
from app.animation_controller import AnimationControllerThread
from app.web_server import WebServerThread

# Paths are relative to the project root (where you run Alis_Script.sh)
MENU_PATH     = "menu.json"
SETTINGS_PATH = "settings.json"

# Default settings applied if settings.json is missing/corrupt
DEFAULT_SETTINGS: Dict[str, Any] = {
    "display": {
        "rotation": 180,              # read once at startup
        "brightness": 100,           # 0..100, applied continuously
        "sleep_seconds": 120,        # backlight off after idle
        "screensaver_enabled": False
    },
    "led": {
        "brightness": 20             # (stub until you wire LEDs)
    },
    "ui": {
        "anim_speed": 5              # (stub; future screensaver/animations)
    },
    "system": {
        "program_select": "Default", # (stub; future launcher)
        "auto_shutdown_min": 0,      # (stub)
        "restart_required": False    # set true when a restart-only setting changes
    },
    "network": {
        "wifi_connected": False,     # (stub; status bar shows basic placeholder)
        "ssid": ""
    }
}


class DebouncedSaver:
    """Debounce writes to settings.json to reduce SD wear."""
    def __init__(self, path: str, delay: float = 0.6):
        self.path = path
        self.delay = delay
        self._timer = None
        self._lock = threading.Lock()

    def __call__(self, data: Dict[str, Any]):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, save_json_atomic, args=(self.path, data))
            self._timer.daemon = True
            self._timer.start()


def main():
    # 1) Load menu spec
    with open(MENU_PATH, "r") as f:
        menu_spec = json.load(f)

    # 2) Load settings (merge defaults, write file if missing/corrupt)
    settings: Dict[str, Any] = load_json(SETTINGS_PATH, DEFAULT_SETTINGS)

    # If a previous run marked restart_required, clear it now that we've restarted successfully
    if settings.get("system", {}).get("restart_required"):
        settings["system"]["restart_required"] = False
        save_json_atomic(SETTINGS_PATH, settings)

    # 3) Create debounced saver so menu edits persist without spamming disk
    save_cb = DebouncedSaver(SETTINGS_PATH, delay=0.6)

    # Helper to expose settings to other threads
    def get_settings() -> Dict[str, Any]:
        return settings

    # Create stop event and threads early so menu actions can reference them
    stop_evt = threading.Event()
    anim_thread = AnimationControllerThread(stop_evt=stop_evt)
    web_thread = WebServerThread(stop_evt=stop_evt, anim_thread=anim_thread)

    # Menu action handler
    def action_handler(name: str) -> None:
        if name == "led.rgb_cycle":
            anim_thread.set_mode("animation")
        elif name == "led.stop":
            anim_thread.set_mode("static")
        else:
            print(f"[Menu] action requested: {name}")

    # 4) Create controller (pure logic) and status provider (for top bar)
    controller = MenuController(menu_spec, settings, save_cb=save_cb, action_cb=action_handler)
    status     = StatusProvider(settings, web_port=web_thread.port)   # pass settings so it can expose "↻" when needed

    # 5) Helpers for the display thread to fetch current theme
    def get_theme() -> Dict[str, str]:
        return menu_spec.get("theme", {"fg": "white", "bg": "black", "accent": "cyan"})

    # 6) Read rotation ONCE from settings and pass into DisplayThread
    rotation = int(settings.get("display", {}).get("rotation", 0)) % 360

    # Resolve assets directory relative to this file
    assets_path = os.path.join(os.path.dirname(__file__), "assets")

    # 7) Spin up threads
    disp_thread = DisplayThread(
        stop_evt=stop_evt,
        controller=controller,
        status_provider=status,
        get_theme=get_theme,
        get_settings=get_settings,
        assets_dir=assets_path,
        rotation=rotation,              # <-- applied once at startup
    )
    btn_thread  = ButtonsThread(stop_evt=stop_evt, controller=controller)


    try:
        disp_thread.start()
        btn_thread.start()
        anim_thread.start()
        web_thread.start()
        # Main thread can host future supervisors/services
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Alis] Shutting down…")
    finally:
        stop_evt.set()
        # Give threads a moment to exit cleanly
        btn_thread.join(timeout=2.0)
        disp_thread.join(timeout=3.0)
        anim_thread.join(timeout=2.0)
        web_thread.join(timeout=2.0)
        # Ensure final settings are flushed
        save_json_atomic(SETTINGS_PATH, settings)
        print("[Alis] Stopped.")


if __name__ == "__main__":
    main()
