import socket
import subprocess
import re

#retrieves wifi list and controls login

def get_local_ip():
    """Return the local IP address of the Pi.
    Returns:
        str: Local IP address (e.g., '192.168.1.10').
        If not connected, returns '127.0.0.1'.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a public IP, doesn't have to be reachable
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def is_connected():
    """Return True if the Pi is connected to a network (has an IP other than 127.0.0.1).
    
    Returns:
        bool: True if connected to a network, False otherwise.
    """
    ip = get_local_ip()
    return ip != '127.0.0.1'

def get_wifi_signal_strength(interface="wlan0"):
    """
    Return the signal strength (RSSI in dBm) of the wireless connection.
    Returns:
        int: Signal strength in dBm (e.g., -45).
        None: If not connected or signal strength not available.
    """
    try:
        output = subprocess.check_output(['iwconfig', interface], encoding='utf-8')
        match = re.search(r'Signal level=(-?\d+) dBm', output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None

def is_connected_wifi(interface="wlan0"):
    """
    Return True if the Pi is connected to a WiFi network (interface has an IP address).
    Returns:
        bool: True if connected to WiFi, False otherwise.
    """
    try:
        output = subprocess.check_output(['ip', 'addr', 'show', interface], encoding='utf-8')
        return "inet " in output
    except Exception:
        return False
    
def get_local_wifi_networks():
    """
    Returns a list of SSIDs of local WiFi networks using nmcli.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "SSID", "dev", "wifi"],
            capture_output=True, text=True, check=True
        )
        # Split lines, remove empty strings, and deduplicate
        ssids = list({ssid for ssid in result.stdout.splitlines() if ssid})
        return ssids
    except Exception as e:
        print(f"Error scanning WiFi networks: {e}")
        return []
    
def get_current_wifi_ssid():
    """
    Returns the SSID of the currently connected WiFi network, or None if not connected.
    """
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            active, ssid = line.split(":", 1)
            if active == "yes":
                return ssid
        return None
    except Exception as e:
        print(f"Error getting current WiFi SSID: {e}")
        return None
    
def is_wifi_enabled():
    """
    Returns True if WiFi is enabled, False otherwise.
    """
    try:
        result = subprocess.run(
            ["nmcli", "radio", "wifi"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip().lower() == "enabled"
    except Exception as e:
        print(f"Error checking WiFi status: {e}")
        return False