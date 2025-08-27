from unittest.mock import patch

from app.led_controller import LEDThread, Color


def test_set_all_updates_strip_and_updates():
    thread = LEDThread.__new__(LEDThread)
    thread.count = 3

    class DummyStrip:
        def __init__(self):
            self.calls = []
            self.update_called = 0

        def set_led_color(self, i, r, g, b):
            self.calls.append((i, (r, g, b)))

        def update_strip(self):
            self.update_called += 1

    thread.strip = DummyStrip()
    thread._set_all(Color(1, 2, 3))

    assert thread.strip.calls == [
        (0, Color(1, 2, 3)),
        (1, Color(1, 2, 3)),
        (2, Color(1, 2, 3)),
    ]
    assert thread.strip.update_called == 1


def test_run_fills_and_clears_on_exit():
    settings = {"led": {"brightness": 5}}

    class DummyStop:
        def is_set(self):
            return False

    class DummyStrip:
        def __init__(self):
            self.calls = []
            self.update_calls = 0
            self.clear_called = 0

        def set_led_color(self, i, r, g, b):
            self.calls.append((i, (r, g, b)))

        def update_strip(self):
            self.update_calls += 1

        def clear_strip(self):
            self.clear_called += 1

    thread = LEDThread(stop_evt=DummyStop(), get_settings=lambda: settings, count=3)
    thread.strip = DummyStrip()

    with patch('time.sleep', lambda s: None):
        thread.run()

    expected_color = Color(0, 5, 0)
    assert thread.strip.calls == [
        (0, expected_color),
        (1, expected_color),
        (2, expected_color),
    ]
    # 3 updates for pixels + 1 after clearing
    assert thread.strip.update_calls == 4
    assert thread.strip.clear_called == 1
