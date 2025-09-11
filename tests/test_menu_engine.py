import json
import os

from app.menu_engine import MenuController


def test_screen_brightness_rotates():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    with open(os.path.join(root, 'menu.json')) as f:
        menu_spec = json.load(f)

    settings = {"display": {"brightness": 25}}
    mc = MenuController(menu_spec, settings, lambda s: None)

    # Navigate to Settings -> Screen Brightness
    mc.on_event("DOWN")
    mc.on_event("DOWN")   # focus Settings on home screen
    mc.on_event("SELECT") # enter Settings
    mc.on_event("DOWN")   # move focus to Screen Brightness item

    for expected in [50, 75, 100, 25]:
        mc.on_event("SELECT")
        assert settings["display"]["brightness"] == expected
