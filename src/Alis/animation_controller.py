# animation_controller.py

import time
import queue
import threading
from multiprocessing import Queue
import h5py
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#hard coded pixels init and brightness 

class AnimationController(threading.Thread):

    # Only one mapping: vertical zigzag (serpentine) columns, start bottom left
    def remap_matrix(self, frame):
        """
        Remap a 2D frame (numpy array) to a flat list of (r, g, b) tuples for vertical zigzag columns,
        starting from the bottom left (column 0, row h-1), matching Teensy's flat strip order.
        """
        h, w, _ = frame.shape
        remapped = []
        for x in range(w):
            if x % 2 == 0:
                # Even column: bottom to top
                for y in range(h-1, -1, -1):
                    remapped.append(tuple(frame[y, x]))
            else:
                # Odd column: top to bottom
                for y in range(h):
                    remapped.append(tuple(frame[y, x]))
        return remapped

    @staticmethod
    def gamma_correct(value, gamma=2.2):
        return int(pow(value / 255.0, gamma) * 255 + 0.5)
    def __init__(self, stop_evt, frame_queue,
                current_settings, settings_lock,web_animation_queue, show_animation_qeue, show_entry_complete_event, interface_animation_queue):
        super().__init__(name="AnimationControllerThread")
        self.shutdown_event = stop_evt
        self.frame_queue = frame_queue
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        #queues communication
        self.web_animation_queue = web_animation_queue
        self.show_animation_qeue = show_animation_qeue
        self.interface_animation_queue = interface_animation_queue

        self.mode = "idle"
        self.pixels = 256
        self.width = 14
        self.height = 50
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

        self.set_idle()

    def set_idle(self):
        with self.settings_lock:
            self.current_settings["Animation Mode"] = "idle"
    
    def get_brightness(self):
        with self.settings_lock:
            self.brightness = self.current_settings["LED Brightness"]

    #set new mode in current settings
    def set_mode(self, new_mode):
        with self.settings_lock:
            self.current_settings["Animation Mode"] = new_mode

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
        from pathlib import Path
        import numpy as np
        from PIL import Image, ImageDraw, ImageFont

        def _load_font(font_px: int) -> ImageFont.FreeTypeFont:
            here = Path(__file__).resolve().parent
            candidates = [
                here / "assets" / "DejaVuSans-Bold.ttf",
                here.parent / "assets" / "DejaVuSans-Bold.ttf",
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            ]
            for p in candidates:
                if p.exists():
                    try:
                        return ImageFont.truetype(str(p), font_px)
                    except OSError:
                        pass
            return ImageFont.load_default()

        SCALE = 4  # supersample scale for better legibility
        Ws, Hs = width * SCALE, height * SCALE

        # Load font at scaled size
        font = _load_font(font_size * SCALE)

        # Measure text precisely (textbbox > textsize)
        tmp = Image.new("RGB", (1, 1), (0, 0, 0))
        dtmp = ImageDraw.Draw(tmp)
        try:
            l, t, r, b = dtmp.textbbox((0, 0), text, font=font)
        except AttributeError:
            # Older Pillow fallback
            tw, th = dtmp.textsize(text, font=font)
            l, t, r, b = 0, 0, tw, th
        text_w, text_h = r - l, b - t

        # Add margins so it scrolls in from off-screen and exits fully
        margin = Ws  # one screen width margin on each side
        img_w = margin + text_w + margin
        canvas = Image.new("RGB", (img_w, Hs), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # Center vertically
        y = (Hs - text_h) // 2
        draw.text((margin - l, y - t), text, font=font, fill=color)

        frames = []
        # Move by scaled pixels so scroll_speed=1 is one LED pixel step
        step = max(1, int(scroll_speed) * SCALE)
        for offset in range(0, img_w - Ws + 1, step):
            frame = canvas.crop((offset, 0, offset + Ws, Hs))
            # Downsample to panel size
            frame_small = frame.resize((width, height), Image.LANCZOS)
            arr = np.asarray(frame_small, dtype=np.uint8)

            # RGB -> GRB for your strip order
            grb_arr = arr[..., [1, 0, 2]]
            frames.append(grb_arr)

        return frames

    def run(self):
        try:
            while not self.shutdown_event.is_set():
                msg = None
                with self.settings_lock:
                    print(self.current_settings)
                try:
                    msg = self.show_animation_qeue.get(timeout=0.05)
                except queue.Empty:
                    pass
                if msg is None:
                    try:
                        msg = self.web_animation_queue.get(timeout=0.05)
                    except queue.Empty:
                        pass
                if msg is None:
                    try:
                        msg = self.interface_animation_queue.get(timeout=0.05)
                    except queue.Empty:
                        pass    

                # Handle mode change message
                if msg and isinstance(msg, dict) and msg.get("type") == "mode":
                    new_mode = msg.get("mode")
                    if new_mode != self.mode:
                        self.mode = new_mode
                        self.set_mode(new_mode)
                        print(f"Mode changed to {self.mode}")
                        self.frame_count = 0
                    continue  # Restart loop with new mode

                match self.mode:
                    case "idle":
                        print("animation controller idle")
                        time.sleep(5.0)
                    case "test":
                        print("animation controller test (matrix-based)")
                        h, w = self.height, self.width
                        # Helper to send a matrix using remap_matrix and gamma correction
                        def send_matrix(matrix):
                            remapped = self.remap_matrix(matrix)
                            payload = bytearray()
                            for r, g, b in remapped:
                                r_corr = self.gamma_correct(r)
                                g_corr = self.gamma_correct(g)
                                b_corr = self.gamma_correct(b)
                                payload.extend([r_corr, g_corr, b_corr])
                            self.frame_queue.put(bytes(payload))

                        # Solid red
                        matrix = np.zeros((h, w, 3), dtype=np.uint8)
                        matrix[..., 0] = 255
                        send_matrix(matrix)
                        time.sleep(1)
                        # Solid green
                        matrix = np.zeros((h, w, 3), dtype=np.uint8)
                        matrix[..., 1] = 255
                        send_matrix(matrix)
                        time.sleep(1)
                        # Solid blue
                        matrix = np.zeros((h, w, 3), dtype=np.uint8)
                        matrix[..., 2] = 255
                        send_matrix(matrix)
                        time.sleep(1)

                        # Light up each physical LED in remap_matrix order, leave them on, use green
                            # Use a numpy array for the frame, light up one more LED each time, remap for output
                        matrix = np.zeros((h, w, 3), dtype=np.uint8)
                        n_leds = h * w
                        frame_interval = 1.0 / 30.0  # 30 FPS
                        for y in range(h):
                            for x in range(w):
                                t_start = time.time()
                                matrix[y, x] = [0, 255, 0]  # green
                                remapped = self.remap_matrix(matrix)
                                payload = bytearray()
                                for r, g, b in remapped:
                                    r_corr = self.gamma_correct(r)
                                    g_corr = self.gamma_correct(g)
                                    b_corr = self.gamma_correct(b)
                                    payload.extend([r_corr, g_corr, b_corr])
                                self.frame_queue.put(bytes(payload))
                                t_elapsed = time.time() - t_start
                                if t_elapsed < frame_interval:
                                    time.sleep(frame_interval - t_elapsed)
                    case "draw":
                        if msg == "clear":
                            self.frame_queue.put(bytes([0, 0, 0]) * self.pixels)
                            print("Canvas cleared")
                        elif msg and isinstance(msg, dict) and msg.get("type") == "matrix":
                            matrix = msg["matrix"]
                            payload = bytearray()
                            for x in range(self.width):
                                for y in range(self.height):
                                    r, g, b = matrix[x][y]
                                    r_corr = self.gamma_correct(r)
                                    g_corr = self.gamma_correct(g)
                                    b_corr = self.gamma_correct(b)
                                    payload.extend([g_corr, r_corr, b_corr])
                            self.frame_queue.put(bytes(payload))
                    case "static":
                        # Handle new image messages
                        if msg and isinstance(msg, dict):
                            if msg.get("type") == "image":
                                self.image_name = msg.get("name")
                                h5_path = os.path.join(BASE_DIR, "uploaded", "images", self.image_name)
                                print("new image")
                                with h5py.File(h5_path, "r") as h5f:
                                    dset = h5f["frames"]
                                    self.image_matrix = dset[...]
                                    self.seconds_requested = -1  # Show indefinitely
                                    self.seconds_shown = 0
                                # Send image once
                                frame = self.image_matrix[0] if self.image_matrix.ndim == 4 else self.image_matrix
                                payload = bytearray()
                                remapped = self.remap_matrix(frame)
                                for r, g, b in remapped:
                                    r_corr = self.gamma_correct(r)
                                    g_corr = self.gamma_correct(g)
                                    b_corr = self.gamma_correct(b)
                                    payload.extend([r_corr, g_corr, b_corr])
                                self.frame_queue.put(bytes(payload))

                            elif msg.get("type") == "show_image":
                                self.image_name = msg.get("name")
                                seconds = int(msg.get("seconds", 5))
                                h5_path = os.path.join(BASE_DIR, "uploaded", "images", self.image_name)
                                print("show image")
                                with h5py.File(h5_path, "r") as h5f:
                                    dset = h5f["frames"]
                                    self.image_matrix = dset[...]
                                    self.seconds_requested = seconds
                                    self.seconds_shown = 0
                                # Send image once
                                frame = self.image_matrix[0] if self.image_matrix.ndim == 4 else self.image_matrix
                                payload = bytearray()
                                for x in range(self.width):
                                    for y in range(self.height):
                                        g, r, b = frame[y, x]
                                        r_corr = self.gamma_correct(r)
                                        g_corr = self.gamma_correct(g)
                                        b_corr = self.gamma_correct(b)
                                        payload.extend([r_corr, g_corr, b_corr])
                                self.frame_queue.put(bytes(payload))

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
                                h5_path = os.path.join(BASE_DIR, "uploaded", "animations", filename)
                                print("new animation")
                                with h5py.File(h5_path, "r") as h5f:
                                    if "frames" not in h5f:
                                        raise ValueError(f"No 'frames' dataset in {h5_path}")
                                    dset = h5f["frames"]
                                    print("frames type:", type(dset))
                                    if not isinstance(dset, h5py.Dataset):
                                        raise TypeError(f"'frames' is not a dataset in {h5_path}, got {type(dset)}")
                                    self.animation_frames = dset[...]
                                    if self.animation_frames.ndim == 3:
                                        # Normalize single-frame to (F,H,W,C)
                                        self.animation_frames = self.animation_frames[None, ...]
                                    if self.animation_frames.shape[-1] != 3:
                                        raise ValueError(f"Expected last channel size 3 (RGB/GRB), got {self.animation_frames.shape}")
                                    self.total_frames = self.animation_frames.shape[0]
                                    self.animation_name = filename
                                    self.animation_index = 0
                                    self.loop_counter = 0
                                    self.loops_reqested = -1  # Loop forever for direct animation messages
                                    print(f"Animation {filename} has {self.total_frames} frames")
                            elif msg.get("type") == "show_animation":
                                filename = msg.get("name")
                                loops_requested = int(msg.get("loops_requested", 1))
                                h5_path = os.path.join(BASE_DIR, "uploaded", "animations", filename)
                                print("show animation")
                                with h5py.File(h5_path, "r") as h5f:
                                    if "frames" not in h5f:
                                        raise ValueError(f"No 'frames' dataset in {h5_path}")
                                    dset = h5f["frames"]
                                    print("frames type:", type(dset))
                                    if not isinstance(dset, h5py.Dataset):
                                        raise TypeError(f"'frames' is not a dataset in {h5_path}, got {type(dset)}")
                                    self.animation_frames = dset[...]
                                    if self.animation_frames.ndim == 3:
                                        self.animation_frames = self.animation_frames[None, ...]
                                    if self.animation_frames.shape[-1] != 3:
                                        raise ValueError(f"Expected last channel size 3 (RGB/GRB), got {self.animation_frames.shape}")
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
                                remapped = self.remap_matrix(matrix)
                                for r, g, b in remapped:
                                    r_corr = self.gamma_correct(r)
                                    g_corr = self.gamma_correct(g)
                                    b_corr = self.gamma_correct(b)
                                    payload.extend([r_corr, g_corr, b_corr])
                                self.frame_queue.put(bytes(payload))
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
                                text_json_path = os.path.join(BASE_DIR, "data", "text_display.json")
                                with open(text_json_path, "r") as f:
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
                                    remapped = self.remap_matrix(frame)
                                    for r, g, b in remapped:
                                        r_corr = self.gamma_correct(r)
                                        g_corr = self.gamma_correct(g)
                                        b_corr = self.gamma_correct(b)
                                        payload.extend([r_corr, g_corr, b_corr])
                                    self.frame_queue.put(bytes(payload))
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
        dset = h5f["frames"]
        print("frames type:", type(dset))
        if not isinstance(dset, h5py.Dataset):
            raise TypeError(f"'frames' is not a dataset in {h5_file}, got {type(dset)}")
        matrix = dset[frame_idx, ...]  # shape: (height, width, 3)
    return matrix