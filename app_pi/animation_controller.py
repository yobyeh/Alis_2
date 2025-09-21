# animation_controller.py

import time
import queue
import threading
from multiprocessing import Queue
import h5py
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json

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

        #animantion tracking
        self.animation_frames = None
        self.animation_name = None
        self.animation_index = 0
        self.total_frames = 0

        #scrolling text
        self.display_text = ""
        #self.draw_matrix = self.new_draw_matrix()

    def get_brightness(self):
        with self.settings_lock:
            self.brightness = self.current_settings["LED brightness"]

    #set new mode in current settings
    def set_mode(self):
        with self.settings_lock:
            self.current_settings["Animation Mode"] = self.mode

    def convert_html_to_GRB(self):
        pass
    
    # #make blank draw matrix
    # def new_draw_matrix(self):
    #     matrix = []
    #     for x in range(self.width):
    #         row = []
    #         for y in range(self.height):
    #             row.append(0)
    #         matrix.append(row)
    #     return matrix

    #transform xy limit 100 to current pixels 
    def trans_100xy(self, xy):
        x, y = xy
        px = round(x / 100 * (self.width - 1))
        py = round(y / 100 * (self.height - 1))
        return px, py
    
    def render_scrolling_text(self, text, width, height, color="#ffd600", font_size=32, scroll_speed=1):
        # Render text to a long image
        img = Image.new("RGB", (width*8 + len(text)*font_size, height*4), (0, 0, 0))
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        w, h = draw.textsize(text, font=font)
        draw.text((width*4, (img.height-h)//2), text, font=font, fill=color)
        # Scroll window across the image
        frames = []
        for offset in range(0, img.width-width+1, scroll_speed):
            frame = img.crop((offset, 0, offset+width, height*4))
            frame_small = frame.resize((width, height), Image.LANCZOS)
            arr = np.array(frame_small)
            grb_arr = np.zeros_like(arr)
            grb_arr[..., 0] = arr[..., 1]  # G
            grb_arr[..., 1] = arr[..., 0]  # R
            grb_arr[..., 2] = arr[..., 2]  # B
            frames.append(grb_arr)
        return frames

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
                    self.frame_count = 0
                    continue  # Restart loop with new mode

                match self.mode:
                    case "idle":
                        print("animation controller idle")
                        time.sleep(5.0)
                    case "test":
                        print("animation controller test")
                        self.frame_queue.put((bytes([0, 255, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([255, 0, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([0, 0, 255]) * self.pixels, self.brightness))
                        time.sleep(2)
                    case "draw":
                        if msg == "clear":
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
                    case "animation":
                        # If a new animation message arrives, load the animation
                        if msg and isinstance(msg, dict) and msg.get("type") == "animation":
                            filename = msg.get("name")
                            h5_path = f"uploaded/animations/{filename}"
                            print("new animation")
                            with h5py.File(h5_path, "r") as h5f:
                                if "frames" not in h5f:
                                    raise ValueError(f"No 'frames' dataset in {h5_path}")
                                frames = h5f["frames"]
                                print("frames type:", type(frames))
                                if not isinstance(frames, h5py.Dataset):
                                    raise TypeError(f"'frames' is not a dataset in {h5_path}, got {type(frames)}")
                                self.animation_frames = np.array(frames)
                                self.total_frames = self.animation_frames.shape[0]
                                self.animation_name = filename
                                self.animation_index = 0
                                print(f"Animation {filename} has {self.frame_count} frames")

                        # If animation is loaded, loop through frames
                        if self.animation_frames is not None and self.frame_count > 0:
                            matrix = self.animation_frames[self.animation_index]
                            payload = bytearray()
                            for x in range(self.width):
                                for y in range(self.height):
                                    g, r, b = matrix[y, x]
                                    payload.extend([g, r, b])
                            self.frame_queue.put((bytes(payload), self.brightness))
                            self.animation_index = (self.animation_index + 1) % self.frame_count
                    case "text":
                        # If a new text message arrives, set the display text
                        if msg and isinstance(msg, dict) and msg.get("type") == "text":
                            self.display_text = msg.get("name")

                        # Load parameters from text_display.json
                        text_params = None
                        if self.display_text:
                            with open("data/text_display.json", "r") as f:
                                text_entries = json.load(f)
                            for entry in text_entries:
                                if entry.get("name") == self.display_text:
                                    text_params = entry
                                    break

                        if text_params:
                            text_height = int(text_params.get("height", self.height))
                            text_width = int(text_params.get("width", self.width))
                            text_color = text_params.get("color", "#ffd600")
                            font_size = int(text_params.get("font size", 32))
                            scroll_speed = int(text_params.get("scroll speed", 2))
                            frames = self.render_scrolling_text(
                                self.display_text, text_width, text_height, text_color, font_size, scroll_speed
                            )
                            for frame in frames:
                                payload = bytearray()
                                for x in range(text_width):
                                    for y in range(text_height):
                                        g, r, b = frame[y, x]
                                        payload.extend([g, r, b])
                                self.frame_queue.put((bytes(payload), self.brightness))
                                time.sleep(0.05)
                        else:
                            print("No matching text entry found or no text to display")
                    case _:
                        print("invalid animation mode")

                time.sleep(0.05) # frame rate
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