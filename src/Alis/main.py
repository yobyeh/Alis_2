# main.py
# owns interface,

import json
import threading
import logging
from pathlib import Path
import time
import multiprocessing
import queue
import signal
from multiprocessing import Manager, Lock
import os

from interface import start_interface  # def start_interface(settings: dict, shutdown_event, lock)
from led_controller import LEDController
from animation_controller import AnimationController
from show_controller import ShowController

BASE_DIR = Path(__file__).parent

MENU_PATH = BASE_DIR / "data" / "menu_data.json"
SETTINGS_PATH = BASE_DIR / "data" / "settings.json"
base = BASE_DIR / "uploaded"

settings_lock = threading.Lock()
# possibly not used yet, passed to interface ????
settings_changed = threading.Event()
shutdown_event = threading.Event()
# animation to led controller
frame_queue = queue.Queue()
# web to animation controller
web_animation_queue = multiprocessing.Queue()
# show controller to animation
show_animation_queue = queue.Queue()
# web to show controller
web_show_queue = multiprocessing.Queue()
# main to web initially sending current settings
main_web_queue = multiprocessing.Queue()
# animation controller completing events from show
show_entry_complete_event = threading.Event()
# interface to web_server for current settings
interface_web_queue = multiprocessing.Queue()
# web to interface for settings change
web_interface_queue = multiprocessing.Queue()

# interface to animation controller
interface_animation_queue = queue.Queue()
# interface to show controller
interface_show_queue = queue.Queue()
# menu to main shutdown queue
menu_main_queue = queue.Queue()

manager = Manager()
interface_web_queue = manager.Queue()
current_settings = manager.dict({"Animation Mode": "idle"})
settings_lock = Lock()


def load_settings() -> dict:
    menu_data = []
    # find menu data
    if not SETTINGS_PATH.exists():
        if MENU_PATH.exists():
            with open(MENU_PATH, "r") as f:
                menu_data = json.load(f)
        else:
            raise FileNotFoundError(f"Menu file not found: {MENU_PATH}")
        # build new settings file with defaults
        new_settings = {}
        for setting, setting_data in menu_data["home"]["Settings"].items():
            default_value = setting_data.get("default")
            if default_value != -1:
                new_settings.update({setting: default_value})
        for setting, setting_data in menu_data["home"]["LED Config"].items():
            default_value = setting_data.get("default")
            if default_value != -1:
                new_settings.update({setting: default_value})

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


def run_web_server(
    web_animation_queue,
    current_settings,
    settings_lock,
    interface_web_queue,
    web_interface_queue,
):
    import uvicorn
    import web_server
    # web servers get communication queues here
    web_server.app.state.web_animation_queue = web_animation_queue
    web_server.app.state.web_show_queue = web_show_queue
    web_server.app.state.current_settings = current_settings
    web_server.app.state.settings_lock = settings_lock
    web_server.app.state.interface_web_queue = interface_web_queue
    web_server.app.state.web_interface_queue = web_interface_queue
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=False)



def start_web_server_monitor(
    web_animation_queue,
    web_show_queue,
    current_settings,
    settings_lock,
    interface_web_queue,
    web_interface_queue,
):
    from multiprocessing import Event
    web_server_shutdown_event = Event()
    while not shutdown_event.is_set():
        proc = multiprocessing.Process(
            target=_run_web_server_graceful,
            args=(
                web_animation_queue,
                web_show_queue,
                current_settings,
                settings_lock,
                interface_web_queue,
                web_interface_queue,
                web_server_shutdown_event,
            ),
        )
        proc.start()
        print("Web server started.")
        while proc.is_alive() and not shutdown_event.is_set():
            time.sleep(0.5)
        if shutdown_event.is_set():
            print("Signaling web server for graceful shutdown...")
            web_server_shutdown_event.set()
            proc.join(timeout=10)
            if proc.is_alive():
                print("Web server did not exit in time, terminating.")
                proc.terminate()
                proc.join()
            print("Web server monitor exiting due to shutdown.")
            break
        print("Web server crashed or exited, restarting in 5s...")
        time.sleep(5)

def _run_web_server_graceful(web_animation_queue, web_show_queue, current_settings, settings_lock, interface_web_queue, web_interface_queue, shutdown_event):
    import web_server_graceful
    web_server_graceful.run_web_server_with_shutdown(
        web_animation_queue,
        web_show_queue,
        current_settings,
        settings_lock,
        interface_web_queue,
        web_interface_queue,
        shutdown_event,
    )


def ensure_uploaded_folders():
    base = Path("uploaded")
    subfolders = [
        "animations",
        "images",
        "images/preview",
        "animations/preview",
        "raw",
    ]
    if not base.exists():
        base.mkdir()
        print(f"Created folder: {base}")
    for sub in subfolders:
        sub_path = base / sub
        if not sub_path.exists():
            sub_path.mkdir(parents=True)
            print(f"Created subfolder: {sub_path}")


def cleanup_gpio():
    try:
        from gpiozero import Device
        if Device.pin_factory:
            Device.pin_factory.close()
            print("GPIO cleaned up.", flush=True)
        else:
            print("No GPIO pin factory active.", flush=True)
    except Exception as e:
        print(f"GPIO cleanup failed: {e}", flush=True)

# Thread to monitor menu_main_queue for shutdown
def menu_shutdown_monitor():
    while not shutdown_event.is_set():
        try:
            msg = menu_main_queue.get(timeout=0.5)
            if isinstance(msg, dict) and msg.get("type") == "shutdown":
                print("Shutdown requested from menu.", flush=True)
                shutdown_event.set()
                # Schedule system shutdown for 30 seconds from now
                os.system("sudo shutdown -h +1")
                break
        except Exception:
            pass

def main():
    cleanup_gpio()  # Ensure GPIO is released from any previous run
    logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(threadName)s] %(message)s",
)
    global current_settings
    current_settings = load_settings()
    print("Alis starting...", flush=True)

    ensure_uploaded_folders()

    # -------------------- Start interface thread --------------------
    interface_thread = threading.Thread(
        target=start_interface,
        args=(
            current_settings,
            shutdown_event,
            settings_lock,
            settings_changed,
            interface_web_queue,
            web_interface_queue,
            interface_animation_queue,
            interface_show_queue,
            menu_main_queue,
        ),
        name="InterfaceThread",
        daemon=False,
    )
    interface_thread.start()
    print("Interface thread started.", flush=True)

    # -------------------- Start LED controller thread --------------------
    led_controller = LEDController(
        stop_evt=shutdown_event,
        frame_queue=frame_queue,
        current_settings=current_settings,
        settings_lock=settings_lock,
    )
    led_controller.start()
    print("LED controller thread started.", flush=True)

    # -------------------- Start animation controller thread --------------------
    animation_controller = AnimationController(
        stop_evt=shutdown_event,
        frame_queue=frame_queue,
        current_settings=current_settings,
        settings_lock=settings_lock,
        web_animation_queue=web_animation_queue,
        show_animation_qeue=show_animation_queue,
        show_entry_complete_event=show_entry_complete_event,
        interface_animation_queue=interface_animation_queue,
    )
    animation_controller.start()
    print("Animation controller thread started.", flush=True)

    # -------------------- Start show controller thread --------------------
    show_controller = ShowController(
        web_show_queue,
        show_animation_queue,
        show_entry_complete_event,
        interface_show_queue,
        shutdown_event=shutdown_event
    )
    show_controller.start()
    print("Show controller thread started.", flush=True)

    # -------------------- Start web server monitor --------------------
    web_server_monitor = multiprocessing.Process(
        target=start_web_server_monitor,
        args=(
            web_animation_queue,
            web_show_queue,
            current_settings,
            settings_lock,
            interface_web_queue,
            web_interface_queue,
        ),
    )
    web_server_monitor.start()
    print("Web server monitor started.", flush=True)

    shutdown_monitor_thread = threading.Thread(target=menu_shutdown_monitor, daemon=True)
    shutdown_monitor_thread.start()


    try:
        # Keep main alive until signaled (or one of the threads ends)
        while (
            interface_thread.is_alive()
            and led_controller.is_alive()
            and animation_controller.is_alive()
            and show_controller.is_alive()
            and not shutdown_event.is_set()
        ):
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Ctrl-C received, shutting down...", flush=True)
        shutdown_event.set()

    # --- Shutdown sequence ---
    print("Waiting for threads to exit...", flush=True)
    # 1) Stop animation (producer) first
    animation_controller.join(timeout=5)
    if animation_controller.is_alive():
        print("Warning: animation_controller did not exit in time.", flush=True)

    # 2) Unblock LED consumer with a sentinel and stop it
    try:
        frame_queue.put_nowait(None)  # sentinel the LED thread recognizes
    except Exception:
        pass
    led_controller.join(timeout=5)
    if led_controller.is_alive():
        print("Warning: led_controller did not exit in time.", flush=True)

    # 3) Stop interface
    interface_thread.join(timeout=5)
    if interface_thread.is_alive():
        print("Warning: interface_thread did not exit in time.", flush=True)

    # 4) Stop show controller
    show_controller.join(timeout=5)
    if show_controller.is_alive():
        print("Warning: show_controller did not exit in time.", flush=True)

    # Stop web server monitor
    if web_server_monitor.is_alive():
        web_server_monitor.terminate()
        web_server_monitor.join(timeout=5)
        print("Web server monitor stopped.", flush=True)

    # Save settings after all threads have stopped
    save_settings()

    # Clean up GPIO
    cleanup_gpio()

    print("main exiting.", flush=True)


if __name__ == "__main__":
    main()