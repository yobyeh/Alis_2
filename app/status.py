# app/status.py
import subprocess
import time
from typing import Dict, Tuple

class StatusProvider:
    def __init__(self, settings: Dict):
        self.settings = settings
        self._last_wifi_check = 0
        self._wifi_cached = (False, "")

    def snapshot(self) -> Dict[str, str]:
        now = time.time()
        if now - self._last_wifi_check > 2:
            try:
                self._wifi_cached = self._read_wifi()
            except Exception:
                # Cache empty result if wifi status cannot be read
                self._wifi_cached = (False, "")
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

    def _read_wifi(self) -> Tuple[bool, str]:
        """Read Wi-Fi status from the operating system.

        Returns:
            Tuple[bool, str]: ``(connected, ssid)``
        """

        # Try NetworkManager first
        try:
            nmcli_out = subprocess.check_output(
                ["nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
                stderr=subprocess.DEVNULL,
            )
            for line in nmcli_out.decode().splitlines():
                parts = line.split(":", 1)
                if len(parts) == 2 and parts[0] == "yes":
                    return True, parts[1]
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Fallback to iwconfig parsing
        try:
            iwconfig_out = subprocess.check_output(
                ["iwconfig"], stderr=subprocess.DEVNULL
            ).decode()
            for line in iwconfig_out.splitlines():
                if "ESSID:" in line:
                    essid = line.split("ESSID:", 1)[1].strip().strip('"')
                    if essid and essid.lower() != "off/any":
                        return True, essid
            return False, ""
        except Exception:
            return False, ""
