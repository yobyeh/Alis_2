import os
import pathlib
from typing import Tuple

try:
    import bluetooth  # type: ignore
except ImportError:  # pragma: no cover - library may not be installed during tests
    bluetooth = None

UPLOAD_DIR = pathlib.Path(__file__).resolve().parent.parent / "uploads"


def _receive_all(sock, size: int) -> bytes:
    """Receive exactly ``size`` bytes from a socket."""
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def run_server() -> None:
    """Run a simple RFCOMM server that saves an incoming file.

    The client should send:
        [2 bytes filename length][filename bytes]
        [8 bytes file size][file bytes]
    """
    if bluetooth is None:
        raise RuntimeError("PyBluez is required for Bluetooth file transfer")

    UPLOAD_DIR.mkdir(exist_ok=True)
    server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server_sock.bind(("", bluetooth.PORT_ANY))
    server_sock.listen(1)
    port = server_sock.getsockname()[1]
    bluetooth.advertise_service(
        server_sock,
        "AlisFileTransfer",
        service_classes=[bluetooth.SERIAL_PORT_CLASS],
        profiles=[bluetooth.SERIAL_PORT_PROFILE],
    )
    print(f"[Receiver] Waiting for connection on RFCOMM channel {port}")
    client_sock, client_info = server_sock.accept()
    print(f"[Receiver] Accepted connection from {client_info}")
    try:
        name_len = int.from_bytes(_receive_all(client_sock, 2), "big")
        filename = _receive_all(client_sock, name_len).decode("utf-8", "ignore")
        size = int.from_bytes(_receive_all(client_sock, 8), "big")
        filepath = UPLOAD_DIR / os.path.basename(filename)
        with open(filepath, "wb") as fh:
            remaining = size
            while remaining > 0:
                chunk = client_sock.recv(min(4096, remaining))
                if not chunk:
                    break
                fh.write(chunk)
                remaining -= len(chunk)
        print(f"[Receiver] Saved {filepath} ({size - remaining} bytes)")
    finally:
        client_sock.close()
        server_sock.close()


if __name__ == "__main__":
    run_server()
