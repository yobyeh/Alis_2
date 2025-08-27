import os
import sys
import time
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Stub out hardware-dependent modules before importing DisplayThread

driver_pkg = types.ModuleType("driver")
lcd_module = types.ModuleType("LCD_2inch")

class DummyLCD:
    def __init__(self):
        self.last = None
    def Init(self):
        pass
    def bl_DutyCycle(self, val):
        self.last = val
    width = 0
    height = 0

lcd_module.LCD_2inch = DummyLCD
driver_pkg.LCD_2inch = lcd_module
sys.modules['driver'] = driver_pkg
sys.modules['driver.LCD_2inch'] = lcd_module

gpiozero_module = types.ModuleType("gpiozero")
class Button:
    pass
gpiozero_module.Button = Button
sys.modules['gpiozero'] = gpiozero_module

# Minimal PIL stub
pil_module = types.ModuleType("PIL")
pil_image_module = types.ModuleType("PIL.Image")
class Image:
    class Transpose:
        ROTATE_270 = ROTATE_180 = ROTATE_90 = 0
    @staticmethod
    def new(mode, size, color):
        return None
pil_image_module.Image = Image
pil_module.Image = pil_image_module
pil_module.ImageDraw = types.SimpleNamespace()
pil_module.ImageFont = types.SimpleNamespace()
sys.modules['PIL'] = pil_module
sys.modules['PIL.Image'] = pil_image_module

from app.interface import DisplayThread


class ApplyBrightnessTest(unittest.TestCase):
    def test_invalid_input_defaults_and_warns(self):
        dt = DisplayThread.__new__(DisplayThread)
        dt.disp = DummyLCD()
        with self.assertLogs(level='WARNING') as log:
            dt._apply_brightness('oops')
        self.assertEqual(dt.disp.last, 100)
        self.assertTrue(any('Invalid brightness value' in m for m in log.output))


class RunLoopSleepTest(unittest.TestCase):
    def test_brightness_not_restored_while_sleeping(self):
        settings = {"display": {"brightness": 77, "sleep_seconds": 1}}

        class DummyStop:
            def __init__(self):
                self.calls = 0

            def is_set(self):
                self.calls += 1
                return self.calls > 1

        dt = DisplayThread.__new__(DisplayThread)
        dt.stop_evt = DummyStop()
        dt.controller = types.SimpleNamespace(last_input_ts=0)
        dt.status = types.SimpleNamespace(snapshot=lambda: {})
        dt.get_theme = lambda: {}
        dt.get_settings = lambda: settings
        dt._screensaver = lambda idle, s: False

        calls = []

        def fake_apply(val):
            calls.append(val)

        dt._apply_brightness = fake_apply

        with patch('time.sleep', lambda s: None):
            dt.run()

        self.assertTrue(calls)
        self.assertEqual(set(calls), {0})


if __name__ == '__main__':
    unittest.main()
