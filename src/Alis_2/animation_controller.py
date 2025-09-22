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
                current_settings, settings_lock,web_animation_queue, show_animation_qeue, show_entry_complete_event):
        super().__init__(name="AnimationControllerThread")
        self.shutdown_event = stop_evt
        self.frame_queue = frame_queue
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        #queues communication
        self.web_animation_queue = web_animation_queue
        self.show_animation_qeue = show_animation_qeue

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
        self.loops_reqested = -1 # loops forever, set if mesage is animation, value if show_animation
        self.loop_counter = 0
        self.show_entry_complete_event = show_entry_complete_event

        #image tracking
        self.seconds_requested = -1
        self.seconds_shown = 0
        self.image_name = None

        #text tracking
        self.text_loops = -1
        self.text_loop_counter = 0
        self.text_name = None

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
                    msg = self.show_animation_qeue.get(timeout=0.1)
                except queue.Empty:
                    pass
                if msg is None:
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
                        # Handle new image messages
                        if msg and isinstance(msg, dict):
                            if msg.get("type") == "image":
                                self.image_name = msg.get("name")
                                h5_path = f"uploaded/images/{self.image_name}"
                                print("new image")
                                with h5py.File(h5_path, "r") as h5f:
                                    matrix = np.array(h5f["frames"])
                                    self.image_matrix = matrix
                                    self.seconds_requested = -1  # Show indefinitely
                                    self.seconds_shown = 0
                                # Send image once
                                frame = self.image_matrix[0] if self.image_matrix.ndim == 4 else self.image_matrix
                                payload = bytearray()
                                for x in range(self.width):
                                    for y in range(self.height):
                                        g, r, b = frame[y, x]
                                        payload.extend([g, r, b])
                                self.frame_queue.put((bytes(payload), self.brightness))

                            elif msg.get("type") == "show_image":
                                self.image_name = msg.get("name")
                                seconds = int(msg.get("seconds", 5))
                                h5_path = f"uploaded/images/{self.image_name}"
                                print("show image")
                                with h5py.File(h5_path, "r") as h5f:
                                    matrix = np.array(h5f["frames"])
                                    self.image_matrix = matrix
                                    self.seconds_requested = seconds
                                    self.seconds_shown = 0
                                # Send image once
                                frame = self.image_matrix[0] if self.image_matrix.ndim == 4 else self.image_matrix
                                payload = bytearray()
                                for x in range(self.width):
                                    for y in range(self.height):
                                        g, r, b = frame[y, x]
                                        payload.extend([g, r, b])
                                self.frame_queue.put((bytes(payload), self.brightness))

                        # Time tracking and completion check
                        if self.image_name and hasattr(self, "image_matrix") and self.seconds_requested > 0:
                            self.seconds_shown += 0.05  # frame rate interval
                            if self.seconds_shown >= self.seconds_requested:
                                if self.show_entry_complete_event:
                                    self.show_entry_complete_event.set()

                    case "animation":
                        if msg and isinstance(msg, dict):
                            if msg.get("type") == "animation":
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
                                    self.loop_counter = 0
                                    self.loops_reqested = -1  # Loop forever for direct animation messages
                                    print(f"Animation {filename} has {self.total_frames} frames")
                            elif msg.get("type") == "show_animation":
                                filename = msg.get("name")
                                loops_requested = int(msg.get("loops_requested", 1))
                                h5_path = f"uploaded/animations/{filename}"
                                print("show animation")
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
                                    self.loop_counter = 0
                                    self.loops_reqested = loops_requested  # Use requested loop count
                                    print(f"Show Animation {filename} has {self.total_frames} frames, loops requested: {self.loops_reqested}")

                        # Only run if animation is loaded
                        if self.animation_frames is not None and self.total_frames > 0:
                            keep_looping = (
                                self.loops_reqested == -1 or
                                self.loop_counter < self.loops_reqested
                            )
                            if keep_looping:
                                matrix = self.animation_frames[self.animation_index]
                                payload = bytearray()
                                for x in range(self.width):
                                    for y in range(self.height):
                                        g, r, b = matrix[y, x]
                                        payload.extend([g, r, b])
                                self.frame_queue.put((bytes(payload), self.brightness))
                                self.animation_index += 1
                                if self.animation_index >= self.total_frames:
                                    self.animation_index = 0
                                    self.loop_counter += 1
                            else:
                                print("Requested loops completed, not looping further.")
                                if self.show_entry_complete_event:
                                    self.show_entry_complete_event.set()

                    case "text":
                        # Handle new text messages
                        if msg and isinstance(msg, dict):
                            self.text_name = msg.get("name", "")
                            self.text_loops = int(msg.get("loops_requested", -1))  # -1 for infinite loops if not provided
                            self.text_loop_counter = 0

                            # Load parameters from text_display.json
                            text_params = None
                            if self.text_name:
                                with open("data/text_display.json", "r") as f:
                                    text_entries = json.load(f)
                                for entry in text_entries:
                                    if entry.get("name") == self.text_name:
                                        text_params = entry
                                        break
                            if text_params:
                                self.text_height = int(text_params.get("height", self.height))
                                self.text_width = int(text_params.get("width", self.width))
                                self.text_color = text_params.get("color", "#ffd600")
                                self.font_size = int(text_params.get("font size", 32))
                                self.scroll_speed = int(text_params.get("scroll speed", 2))
                            else:
                                print("No matching text entry found or no text to display")
                                self.text_name = None

                        # Only render if we have text to display
                        if self.text_name:
                            frames = self.render_scrolling_text(
                                self.text_name, self.text_width, self.text_height, self.text_color, self.font_size, self.scroll_speed
                            )
                            keep_looping = (self.text_loops == -1 or self.text_loop_counter < self.text_loops)
                            if keep_looping:
                                for frame in frames:
                                    payload = bytearray()
                                    for x in range(self.text_width):
                                        for y in range(self.text_height):
                                            g, r, b = frame[y, x]
                                            payload.extend([g, r, b])
                                    self.frame_queue.put((bytes(payload), self.brightness))
                                    time.sleep(0.05)
                                self.text_loop_counter += 1
                                # Only set the event if we've finished all requested loops
                                if self.text_loops != -1 and self.text_loop_counter >= self.text_loops:
                                    print("Requested text loops completed, not looping further.")
                                    if self.show_entry_complete_event:
                                        self.show_entry_complete_event.set()
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