from unittest.mock import patch

from app.led_controller import LEDThread, Color


def test_set_all_updates_strip_and_shows():
    thread = LEDThread.__new__(LEDThread)
    thread.count = 3

    class DummyStrip:
        def __init__(self):
            self.calls = []
            self.show_called = 0

        def setPixelColor(self, i, color):
            self.calls.append((i, color))

        def show(self):
            self.show_called += 1

    thread.strip = DummyStrip()
    thread._set_all(Color(1, 2, 3))

    assert thread.strip.calls == [(0, Color(1, 2, 3)), (1, Color(1, 2, 3)), (2, Color(1, 2, 3))]
    assert thread.strip.show_called == 1


def test_run_uses_brightness_and_clears_on_exit():
    settings = {"led": {"brightness": 42}}

    class DummyStop:
        def __init__(self):
            self.calls = 0

        def is_set(self):
            self.calls += 1
            return self.calls > 1

    thread = LEDThread.__new__(LEDThread)
    thread.stop_evt = DummyStop()
    thread.get_settings = lambda: settings
    thread.count = 1

    class DummyStrip:
        def __init__(self):
            self.brightness_calls = []

        def setBrightness(self, b):
            self.brightness_calls.append(b)

    thread.strip = DummyStrip()

    colors = []

    def fake_set_all(color):
        colors.append(color)

    thread._set_all = fake_set_all

    with patch('time.sleep', lambda s: None):
        thread.run()

    assert thread.strip.brightness_calls == [42]
    assert colors == [Color(255, 0, 0), Color(0, 0, 0)]
