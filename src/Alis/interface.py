# app/interface.py

# Wiring (BCM):
#   UP -> GPIO17, DOWN -> GPIO22, SELECT -> GPIO23, BACK -> GPIO24

# Requires:
#   - driver/LCD_2inch.py (Waveshare)
#   - gpiozero + lgpio backend (GPIOZERO_PIN_FACTORY=lgpio)

# owns the screen controller,menu controller, and lcd
import time
import threading
from PIL import Image
import PIL.Image as PILImage
from driver.LCD_2inch import LCD_2inch
from gpiozero import Button
from utils import deep_get
import logging
from menu_controller import MenuController
from screen_controller import ScreenController
import multiprocessing
import os
import status_manager
from status_manager import is_connected, get_wifi_signal_strength, get_local_ip

# Quiet all PIL logs:
logging.getLogger("PIL").setLevel(logging.WARNING)

# Button pins (BCM numbering)
BTN_PINS = {"UP": 17, "DOWN": 22, "SELECT": 23, "BACK": 24}
DEBOUNCE_S = 0.05

#lcd settings
RENDER_INTERVAL = 0.1  # seconds
ROTATION = 270          # degrees, read once at startup

STATUS_UPDATE = 20 #seconds = update timer for network status

def draw_frame():
    """Example stub to draw a frame on the LCD."""
    pass

def orient_image(img: Image.Image, lcd) -> Image.Image:
    out = img
    if ROTATION % 360:
        out = out.rotate(ROTATION, expand=True)
    # finally scale to panel dimensions
    out = out.resize((lcd.width, lcd.height))
    return out

def show_splash(lcd, path=None):
    if path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, "assets", "splash.png")
    try:
        splash = Image.open(path).convert("RGB")
        splash = orient_image(splash, lcd)
        lcd.ShowImage(splash)
        time.sleep(2)
    except Exception as e:
        print("Splash skipped:", e, flush=True)

def show_menu(lcd, menu, screen): 
        lcd.ShowImage(menu.get_frame(),lcd)

def start_interface(current_settings: dict, shutdown_event: threading.Event, settings_lock: threading.Lock, interface_que:multiprocessing.Queue, settings_changed: threading.Event):
    print("starting interface", flush=True)

    lcd = None
    buttons = {}
    with settings_lock:
        sleep_timer = current_settings["Sleep Timer"]
    try:
        #setup LCD
        lcd = LCD_2inch()
        lcd.Init()
        with settings_lock:
            lcd.bl_DutyCycle(current_settings["Screen Brightness"])
        show_splash(lcd)
        print("LCD initialized", flush=True)

        #setup menu
        screen = ScreenController(lcd.width, lcd.height, current_settings, settings_lock)
        menu = MenuController(screen, current_settings, settings_lock, settings_changed)
        menu.start_menu()

        screen.connected = status_manager.is_connected()
        screen.signal = status_manager.get_wifi_signal_strength()
        screen.address = status_manager.get_local_ip()


        # Setup buttons with gpiozero
        for name, pin in BTN_PINS.items():
            btn = Button(pin, bounce_time=DEBOUNCE_S)
            buttons[name] = btn
            # Example handlers (could push to a queue or mutate settings)
            btn.when_pressed = lambda n=name:menu.move_pointer(n)

        # --- main loop ---
        last_activity = time.time()
        display_on = True
        last_status_update = 0

        while not shutdown_event.is_set():
            menu_change = menu.get_change()

            # If menu_change, update last_activity
            if menu_change == 1:
                last_activity = time.time()
                # If display is off, turn it back on and reset timer
                if not display_on:
                    lcd.bl_DutyCycle(current_settings["Screen Brightness"])
                    display_on = True
                    print("Display turned ON", flush=True)
                show_menu(lcd, menu, screen)

            # If no activity for sleep_timer seconds, turn off display
            if display_on and (time.time() - last_activity > sleep_timer):
                lcd.ShowImage(screen.clear_screen())
                lcd.bl_DutyCycle(0)
                display_on = False
                print("Display turned OFF (sleep)", flush=True)

            now = time.time()
            if now - last_status_update > STATUS_UPDATE:
                screen.connected = is_connected()
                screen.signal = get_wifi_signal_strength()
                screen.address = get_local_ip()
                last_status_update = now

            # Wait up to RENDER_INTERVAL, but break early if shutdown requested
            if shutdown_event.wait(RENDER_INTERVAL):
                break

        print("interface stopping...", flush=True)

    except Exception as e:
        # Surface exceptions from the thread
        import traceback
        print("Interface error:", e, flush=True)
        traceback.print_exc()

    finally:
        # --- cleanup in all cases ---
        for b in buttons.values():
            try:
                b.close()
            except Exception:
                pass
        try:
            if lcd is not None:
                lcd.clear()  # or lcd.cleanup() if your driver exposes it
        except Exception:
            pass
        print("interface stopped", flush=True)
