import subprocess
from typing import Dict, List


EXPECTED_OK = (
    "Already in use",
    "AlreadyExists",
    "already registered",
)

def _run(cmd: List[str]) -> bool:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return True
    except FileNotFoundError:
        print(f"[Bluetooth] {' '.join(cmd)} not found")
        return False
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode().strip()
        # Treat harmless idempotent cases as success
        if any(s.lower() in err.lower() for s in EXPECTED_OK):
            return True
        try:
            subprocess.run(["sudo", *cmd], check=True, capture_output=True)
            return True
        except FileNotFoundError:
            print(f"[Bluetooth] sudo {' '.join(cmd)} not found")
            return False
        except subprocess.CalledProcessError as exc2:
            err2 = (exc2.stderr or b"").decode().strip()
            if any(s.lower() in err2.lower() for s in EXPECTED_OK):
                return True
            print(f"[Bluetooth] {' '.join(cmd)} failed: {err or err2}")
            return False


def set_power(on: bool) -> bool:
    return _run(["bluetoothctl", "power", "on" if on else "off"])


def set_discoverable(on: bool) -> bool:
    return _run(["bluetoothctl", "discoverable", "on" if on else "off"])


def set_pairable(on: bool) -> bool:
    return _run(["bluetoothctl", "pairable", "on" if on else "off"])


def get_status() -> Dict[str, bool]:
    """Return basic bluetoothctl show status."""
    try:
        out = subprocess.run(
            ["bluetoothctl", "show"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return {"powered": False, "discoverable": False, "pairable": False}
    status = {"powered": False, "discoverable": False, "pairable": False}
    for line in out.splitlines():
        if "Powered:" in line:
            status["powered"] = line.strip().endswith("yes")
        elif "Discoverable:" in line:
            status["discoverable"] = line.strip().endswith("yes")
        elif "Pairable:" in line:
            status["pairable"] = line.strip().endswith("yes")
    return status


def list_paired_devices() -> List[str]:
    try:
        out = subprocess.run(
            ["bluetoothctl", "paired-devices"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []
    devices = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "Device":
            devices.append(parts[1])  # the MAC address
    return devices
