# animation_controller.py

import time
import queue
import threading

#hard coded pixels init
class AnimationController(threading.Thread):
    def __init__(self, stop_evt, frame_queue,
                current_settings, settings_lock):
        super().__init__(name="AnimationControllerThread")
        self.shutdown_event = stop_evt
        self.frame_queue = frame_queue
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        self.mode = "idle"
        self.pixels = 256
        self.brightness = 1

    def set_mode(self):
        with self.settings_lock:
            mode = self.current_settings.get("Animation Mode:")
        self.mode = mode

    def convert_to_GRB(self):
        pass

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
                        pass
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