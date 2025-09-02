import threading

from app.led_controller import LEDThread


def test_set_all_updates_pixels_and_shows():
    thread = LEDThread.__new__(LEDThread)

    class DummyPixel:
        def __init__(self):
            self.fills = []
            self.show_count = 0

        def fill(self, color):
            self.fills.append(color)

        def show(self):
            self.show_count += 1

    thread.px = DummyPixel()
    thread.get_settings = lambda: {"led": {"brightness": 20}}
    thread._set_all((1, 2, 3))

    assert thread.px.fills == [(1, 2, 3)]
    assert thread.px.show_count == 1


def test_run_clears_on_start_when_stopped():
    stop_evt = threading.Event()
    stop_evt.set()

    class DummyPixel:
        def __init__(self):
            self.colors = []
        def fill(self, color):
            self.colors.append(color)
        def show(self):
            pass

    led = LEDThread(stop_evt=stop_evt, get_settings=lambda: {"led": {"brightness": 0}})
    led.px = DummyPixel()
    led.run()

    # When stop is set before run, thread should clear strip once
    assert led.px.colors == [(0, 0, 0)]
