# app/status.py
import subprocess
import time
import socket
from typing import Dict, Tuple, List, Optional, Any

class StatusProvider:
    def __init__(self, settings: Dict, web_port: int = 0):
        self.settings = settings
        self.web_port = web_port
        self._last_wifi_check = 0
        self._wifi_cached = (False, "")
        self._last_ip_check = 0.0
        self._ip_cached: str = ""

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        if now - self._last_wifi_check > 2:
            try:
                self._wifi_cached = self._read_wifi()
            except Exception:
                # Cache empty result if wifi status cannot be read
                self._wifi_cached = (False, "")
            self._last_wifi_check = now
        connected, ssid = self._wifi_cached

        bar_right: List[Tuple[str, Optional[str]]] = []

        wifi_icon = "📶"
        if connected:
            bar_right.append((wifi_icon, None))
        else:
            bar_right.append((wifi_icon, "#606060"))

        if self.settings.get("system", {}).get("restart_required"):
            bar_right.append(("↻", None))

        footer = ""
        if self.web_port:
            if now - self._last_ip_check > 60 or not self._ip_cached:
                try:
                    self._ip_cached = self._get_local_ip()
                except Exception:
                    self._ip_cached = ""
                self._last_ip_check = now
            if self._ip_cached:
                footer = f"http://{self._ip_cached}:{self.web_port}"

        return {
            "time": time.strftime("%H:%M"),
            "wifi": bar_right,
            "footer": footer,
        }

    def _get_local_ip(self) -> str:
        """Best-effort local IP address for constructing a URL."""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()

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
