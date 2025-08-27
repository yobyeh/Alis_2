# app/status.py
import time
from typing import Dict

class StatusProvider:
    def __init__(self, settings: Dict):
        self.settings = settings
        self._last_wifi_check = 0
        self._wifi_cached = (False, "")

    def snapshot(self) -> Dict[str, str]:
        now = time.time()
        if now - self._last_wifi_check > 2:
            self._wifi_cached = self._read_wifi_stub()
            self._last_wifi_check = now
        connected, ssid = self._wifi_cached

        bar_right = []
        if connected: bar_right.append("▂▄▆█")
        else:         bar_right.append("x wifi")

        if self.settings.get("system", {}).get("restart_required"):
            bar_right.append("↻")

        return {
            "time": time.strftime("%H:%M"),
            "wifi": "  ".join(bar_right),
        }

    def _read_wifi_stub(self):
        return (False, "")
