import json
import threading
import logging
from pathlib import Path
import time

from interface import start_interface  # def start_interface(settings: dict, shutdown_event, lock)

MENU_PATH = Path("data/menu_data.json")
DEFAULT_SETTINGS_PATH = Path("data/default_settings.json")
SETTINGS_PATH = Path("data/settings.json")
settings_lock = threading.Lock()
shutdown_event = threading.Event()

def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        if DEFAULT_SETTINGS_PATH.exists():
            SETTINGS_PATH.write_text(DEFAULT_SETTINGS_PATH.read_text())
        else:
            raise FileNotFoundError(f"{DEFAULT_SETTINGS_PATH} not found")
    return json.loads(SETTINGS_PATH.read_text())

def save_settings():
    try:
        with settings_lock:
            SETTINGS_PATH.write_text(json.dumps(current_settings, indent=2))
        print("Settings saved.", flush=True)
    except Exception:
        logging.exception("Failed to save settings")

def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s"
    )

    global current_settings
    current_settings = load_settings()
    print("Overlord starting...", flush=True)

    # Start NON-daemon thread and pass all expected args
    t = threading.Thread(
        target=start_interface,
        args=(current_settings, shutdown_event, settings_lock),
        name="InterfaceThread",
        daemon=False,
    )
    t.start()
    print("Interface thread started.", flush=True)

    try:
        # Keep main alive until signaled (or the thread ends)
        while t.is_alive() and not shutdown_event.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Ctrl-C received, shutting down...", flush=True)
        shutdown_event.set()
    finally:
        shutdown_event.set()
        t.join(timeout=5)
        save_settings()
        print("Overlord exiting.", flush=True)

if __name__ == "__main__":
    main()
