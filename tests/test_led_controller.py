import threading

from app.led_controller import LEDThread, build_solid_grb


class DummySerial:
    def __init__(self):
        self.writes = []
        self.timeout = 0.2

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def flush(self) -> None:
        pass

    def reset_input_buffer(self) -> None:  # pragma: no cover - simple stub
        pass

    def readline(self) -> bytes:  # pragma: no cover - simple stub
        return b""

    def close(self) -> None:  # pragma: no cover - simple stub
        pass


def test_set_all_sends_frame() -> None:
    ser = DummySerial()
    thread = LEDThread(
        stop_evt=threading.Event(),
        get_settings=lambda: {"led": {"brightness": 20}},
        width=1,
        height=1,
        strips_used=1,
        ser=ser,
    )

    thread._set_all((1, 2, 3))

    payload = build_solid_grb(1, 1, 1, (1, 2, 3))
    expected_hdr = bytes((0xAB, 0xCD, 0xF1, 0x00, 1, 0, 20))
    assert ser.writes == [expected_hdr + payload]


def test_run_clears_on_start_when_stopped() -> None:
    stop_evt = threading.Event()
    stop_evt.set()

    class DummyThread(LEDThread):
        def __init__(self):
            self.colors = []
            super().__init__(
                stop_evt=stop_evt,
                get_settings=lambda: {"led": {"brightness": 0}},
                width=1,
                height=1,
                strips_used=1,
                ser=DummySerial(),
            )

        def _set_all(self, color):
            self.colors.append(color)
            super()._set_all(color)

    led = DummyThread()
    led.run()

    # When stop is set before run, thread should clear strip once
    assert led.colors == [(0, 0, 0)]

