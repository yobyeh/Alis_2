# main.py
# owns interface, 

import json
import threading
import logging
from pathlib import Path
import time
import multiprocessing
import queue

from interface import start_interface  # def start_interface(settings: dict, shutdown_event, lock)
from led_controller import LEDController
from animation_controller import AnimationController

MENU_PATH = Path("data/menu_data.json")
#DEFAULT_SETTINGS_PATH = Path("data/default_settings.json")
SETTINGS_PATH = Path("data/settings.json")
settings_lock = threading.Lock()
settings_changed = threading.Event()
shutdown_event = threading.Event()
frame_queue = queue.Queue()

#thread communication
interface_que = multiprocessing.Queue()

def load_settings() -> dict:
    menu_data = []
    #find menu data
    if not SETTINGS_PATH.exists():
        if MENU_PATH.exists():
            with open(MENU_PATH, "r") as f:
                menu_data = json.load(f)
        else:
            raise FileNotFoundError(f"Menu file not found: {MENU_PATH}")        
        #build new settings file with defaults
        new_settings = {}
        for setting, setting_data in menu_data["home"]["Settings"].items():
            default_value = setting_data.get("default")
            #print(setting, default_value, flush=True)
            if default_value != -1:
                new_settings.update({setting: default_value})
        #print(new_settings, flush=True)
        SETTINGS_PATH.write_text(json.dumps(new_settings))
        return new_settings
    else:
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
    global interface_que
    global current_settings
    current_settings = load_settings()
    print("Alis starting...", flush=True)

    # -------------------- Start interface thread --------------------
    interface_thread = threading.Thread(
        target=start_interface,
        args=(current_settings, shutdown_event, settings_lock, interface_que, settings_changed),
        name="InterfaceThread",
        daemon=False,
    )
    interface_thread.start()
    print("Interface thread started.", flush=True)



    # -------------------- Start LED controller thread --------------------
    led_controller = LEDController(
        stop_evt=shutdown_event,
        frame_queue = frame_queue,
        current_settings=current_settings,
        settings_lock=settings_lock
    )
    led_controller.start()
    print("LED controller thread started.", flush=True)

    # -------------------- Start animation controller thread --------------------
    animation_controller = AnimationController(
        stop_evt = shutdown_event,
        frame_queue = frame_queue,
        current_settings = current_settings,
        settings_lock = settings_lock
    )
    animation_controller.start()
    print("Animation controller thread started.", flush=True)

    try:
        # Keep main alive until signaled (or one of the threads ends)
        while (
            interface_thread.is_alive()
            and led_controller.is_alive()
            and animation_controller.is_alive()
            and not shutdown_event.is_set()
        ):
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Ctrl-C received, shutting down...", flush=True)
        shutdown_event.set()
    finally:
        # 1) Stop animation (producer) first
        try:
            animation_controller.join(timeout=5)
        except Exception:
            pass

        # 2) Unblock LED consumer with a sentinel and stop it
        try:
            frame_queue.put_nowait(None)  # sentinel the LED thread recognizes
        except Exception:
            pass
        try:
            led_controller.join(timeout=5)
        except Exception:
            pass

        # 3) Stop interface
        try:
            interface_thread.join(timeout=5)
        except Exception:
            pass

        save_settings()
        print("main exiting.", flush=True)

if __name__ == "__main__":
    main()
