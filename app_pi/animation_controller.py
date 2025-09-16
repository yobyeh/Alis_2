# animation_controller.py

import time
import queue
import threading
from multiprocessing import Queue

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

    def set_mode(self):
        with self.settings_lock:
            mode = self.current_settings.get("Animation Mode:")
        self.mode = mode

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
         # --- main loop ---
            while not self.shutdown_event.is_set():
                self.set_mode()
                match self.mode:
                    case "idle":
                        print("animation controller idle")
                        time.sleep(0.5)
                    case "test":
                        print("animation controller test")
                        self.frame_queue.put((bytes([0, 255, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([255, 0, 0]) * self.pixels, self.brightness))
                        time.sleep(2)
                        self.frame_queue.put((bytes([0, 0, 255]) * self.pixels, self.brightness))
                        time.sleep(2)
                        pass
                    case "show":
                        pass
                    case "draw":
                        try:
                            msg = self.web_animation_queue.get(timeout=0.1)
                            if msg == "clear":
                                self.draw_matrix = self.new_draw_matrix()
                                self.frame_queue.put((bytes([0, 0, 0]) * self.pixels, self.brightness))
                                print("Canvas cleared")
                            elif msg.get("type") == "matrix":
                                matrix = msg["matrix"]
                                # Convert matrix (list of [r,g,b]) to GRB bytes
                                payload = bytearray()
                                for x in range(self.width):
                                    for y in range(self.height):
                                        r, g, b = matrix[x][y]
                                        payload.extend([g, r, b])  # GRB order
                                self.frame_queue.put((bytes(payload), self.brightness))
                            else:
                                pass
                                # x, y = self.trans_100xy((msg['x'], msg['y']))
                                # grb_color = html_to_grb(msg['color'])
                                # self.draw_matrix[x][y] = grb_color
                                # # Build GRB payload from matrix
                                # payload = bytearray()
                                # for x in range(self.width):
                                #     for y in range(self.height):
                                #         val = self.draw_matrix[x][y]
                                #         if val == 0:
                                #             payload.extend([0, 0, 0])
                                #         else:
                                #             payload.extend(val)  # Already GRB
                                # self.frame_queue.put((bytes(payload), self.brightness))
                        except queue.Empty:
                            pass  # No new draw events, just continue
                    case _:
                        #should except
                        print("invalid animation mode")

                
                time.sleep(0.1)
            print("Animation controller stopping...")

        except Exception as e:
            # Surface exceptions from the thread
            import traceback
            print("Interface error:", e, flush=True)
            traceback.print_exc()

def html_to_grb(html_color):
    html_color = html_color.lstrip('#')
    r, g, b = (int(html_color[i:i+2], 16) for i in (0, 2, 4))
    return (g, r, b)