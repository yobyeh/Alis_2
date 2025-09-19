# animation_controller.py

import time
import queue
import threading
from multiprocessing import Queue
import h5py
import numpy as np

#hard coded pixels init and brightness 

class AnimationController(threading.Thread):
    def __init__(self, stop_evt, frame_queue,
                current_settings, settings_lock,web_animation_queue):
        super().__init__(name="AnimationControllerThread")
        self.shutdown_event = stop_evt
        self.frame_queue = frame_queue
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        self.web_animation_queue = web_animation_queue
        self.mode = "idle"
        self.pixels = 256
        self.width = 16
        self.height = 16
        self.brightness = 1
        self.draw_matrix = self.new_draw_matrix()

    def get_brightness(self):
        with self.settings_lock:
            self.brightness = self.current_settings["LED brightness"]

    #set new mode in current settings
    def set_mode(self):
        with self.settings_lock:
            self.current_settings["Animation Mode"] = self.mode

    def convert_html_to_GRB(self):
        pass
    
    #make blank draw matrix
    def new_draw_matrix(self):
        matrix = []
        for x in range(self.width):
            row = []
            for y in range(self.height):
                row.append(0)
            matrix.append(row)
        return matrix

    #transform xy limit 100 to current pixels 
    def trans_100xy(self, xy):
        x, y = xy
        px = round(x / 100 * (self.width - 1))
        py = round(y / 100 * (self.height - 1))
        return px, py

    def run(self):
        try:
            while not self.shutdown_event.is_set():
                msg = None
                try:
                    msg = self.web_animation_queue.get(timeout=0.1)
                except queue.Empty:
                    pass

                # Handle mode change message
                if msg and isinstance(msg, dict) and msg.get("type") == "mode":
                    self.mode = msg.get("mode")
                    self.set_mode()
                    print(f"Mode changed to {self.mode}")
                    continue  # Restart loop with new mode

                match self.mode:
                    case "idle":
                        print("animation controller idle")
                        time.sleep(3.0)
                    case "test":
                        print("animation controller test")
                        self.frame_queue.put((bytes([0, 255, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([255, 0, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([0, 0, 255]) * self.pixels, self.brightness))
                        time.sleep(2)
                    case "show":
                        pass
                    case "draw":
                        if msg == "clear":
                            self.draw_matrix = self.new_draw_matrix()
                            self.frame_queue.put((bytes([0, 0, 0]) * self.pixels, self.brightness))
                            print("Canvas cleared")
                        elif msg and isinstance(msg, dict) and msg.get("type") == "matrix":
                            matrix = msg["matrix"]
                            payload = bytearray()
                            for x in range(self.width):
                                for y in range(self.height):
                                    r, g, b = matrix[x][y]
                                    payload.extend([g, r, b])
                            self.frame_queue.put((bytes(payload), self.brightness))
                    case "static":
                        print("running static")
                        time.sleep(0.5)
                        if msg and isinstance(msg, dict) and msg.get("type") == "image":
                            filename = msg.get("name")
                            h5_path = f"uploaded/images/{filename}"
                            matrix = load_h5_frame_to_matrix(h5_path)
                            payload = bytearray()
                            for x in range(self.width):
                                for y in range(self.height):
                                    g, r, b = matrix[y, x]
                                    payload.extend([g, r, b])
                            self.frame_queue.put((bytes(payload), self.brightness))
                    case _:
                        print("invalid animation mode")

                time.sleep(0.1)
            print("Animation controller stopping...")

        except Exception as e:
            import traceback
            print("Interface error:", e, flush=True)
            traceback.print_exc()

def html_to_grb(html_color):
    html_color = html_color.lstrip('#')
    r, g, b = (int(html_color[i:i+2], 16) for i in (0, 2, 4))
    return (g, r, b)

def load_h5_frame_to_matrix(h5_file, frame_idx=0):
    with h5py.File(h5_file, "r") as h5f:
        if "frames" not in h5f:
            raise ValueError(f"No 'frames' dataset in {h5_file}")
        frames = h5f["frames"]
        print("frames type:", type(frames))
        if not isinstance(frames, h5py.Dataset):
            raise TypeError(f"'frames' is not a dataset in {h5_file}, got {type(frames)}")
        matrix = np.array(frames[frame_idx])  # shape: (height, width, 3)
    return matrix