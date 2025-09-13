# app/interface.py

# Wiring (BCM):
#   UP -> GPIO17, DOWN -> GPIO22, SELECT -> GPIO23, BACK -> GPIO24

# Requires:
#   - driver/LCD_2inch.py (Waveshare)
#   - gpiozero + lgpio backend (GPIOZERO_PIN_FACTORY=lgpio)
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

# Quiet all PIL logs:
logging.getLogger("PIL").setLevel(logging.WARNING)

# Button pins (BCM numbering)
BTN_PINS = {"UP": 17, "DOWN": 22, "SELECT": 23, "BACK": 24}
DEBOUNCE_S = 0.05

#lcd settings
RENDER_INTERVAL = 0.5  # seconds
ROTATION = 270          # degrees, read once at startup

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

def show_splash(lcd, path="assets/splash.png"):
    try:
        splash = Image.open(path).convert("RGB")
        splash = orient_image(splash, lcd)
        lcd.ShowImage(splash)
        time.sleep(.5)
    except Exception as e:
        print("Splash skipped:", e, flush=True)

def show_menu(lcd, menu, screen):
        lcd.ShowImage(orient_image(menu.get_frame(),lcd))

def start_interface(settings: dict, shutdown_event: threading.Event, settings_lock: threading.Lock):
    print("starting interface", flush=True)

    lcd = None
    buttons = {}
    try:
        #setup LCD
        lcd = LCD_2inch()
        lcd.Init()
        with settings_lock:
            lcd.bl_DutyCycle(deep_get(settings, ["display", "backlight"], default=100))
        show_splash(lcd)
        print("LCD initialized", flush=True)

        #setup menu
        screen = ScreenController(lcd.width, lcd.height)
        menu = MenuController(screen)
        menu.start_menu()

        # Setup buttons with gpiozero
        for name, pin in BTN_PINS.items():
            btn = Button(pin, bounce_time=DEBOUNCE_S)
            buttons[name] = btn
            # Example handlers (could push to a queue or mutate settings)
            btn.when_pressed = lambda n=name:menu.move_pointer(n)

        # --- main loop ---
        while not shutdown_event.is_set():

            #draw the menu on screen
            if menu.get_change() == 1:
                show_menu(lcd, menu, screen)
            
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
