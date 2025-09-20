import socket
import subprocess
import re

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