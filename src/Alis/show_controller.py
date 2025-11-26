import time
import threading
import queue
import json
import os
from multiprocessing import Queue


class ShowController(threading.Thread):
    def __init__(self, web_show_queue,
                  show_animation_queue,
                    show_entry_complete_event,
                    interface_show_queue,
                    shows_json_path=None
                    ):
        super().__init__()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if shows_json_path is None:
            shows_json_path = os.path.join(base_dir, "data", "shows.json")
        self.shows_json_path = shows_json_path
        self.web_show_queue = web_show_queue  # Receives commands from web server
        self.animation_queue = show_animation_queue  # Sends entries to AnimationController
        self.current_show = None
        self.show_index = 0
        self.shutdown_event = threading.Event()
        self.show_entry_complete_event = show_entry_complete_event
        self.interface_show_queue = interface_show_queue

    def load_shows(self):
        with open(self.shows_json_path, "r") as f:
            return json.load(f)

    def run(self):
        while not self.shutdown_event.is_set():
            try:
                msg = None
                try:
                    msg = self.web_show_queue.get(timeout=0.2)
                except queue.Empty:
                    pass
                try:
                    msg = self.interface_show_queue.get(timeout=0.2)
                except queue.Empty:
                    pass
                
                if msg:
                    if msg.get("type") == "play_show":
                        show_name = msg.get("name")
                        shows = self.load_shows().get("shows", [])
                        show = next((s for s in shows if s["name"] == show_name), None)
                        if show:
                            self.current_show = show
                            self.show_index = 0
                            print(f"Starting show: {show_name}")
                    elif msg.get("type") == "stop":
                        self.current_show = None
                        print("ShowController: Received stop command, going idle.")
                    elif msg.get("type") == "idle":
                        self.current_show = None
                        print("ShowController: Received idle command, going idle.")
                    elif msg.get("type") == "shutdown":
                        self.shutdown_event.set()

                # If a show is active, loop through its entries
                while self.current_show and self.show_index < len(self.current_show.get("entries", [])):
                    entry = self.current_show["entries"][self.show_index]
                    entry_type = entry.get("type")
                    print(f"Playing entry {self.show_index+1}/{len(self.current_show['entries'])}: {entry_type}")

                    # Send mode change message
                    if entry_type == "static":
                        self.animation_queue.put({"type": "mode", "mode": "static"})
                        self.animation_queue.put({
                            "type": "show_image",
                            "name": entry.get("name"),
                            "seconds": entry.get("seconds", 5)
                        })
                    elif entry_type == "animation":
                        self.animation_queue.put({"type": "mode", "mode": "animation"})
                        self.animation_queue.put({
                            "type": "show_animation",
                            "name": entry.get("name"),
                            "loops_requested": entry.get("loop_count", 1)
                        })
                    elif entry_type == "text":
                        self.animation_queue.put({"type": "mode", "mode": "text"})
                        self.animation_queue.put({
                            "type": "show_text",
                            "name": entry.get("name"),
                            "loops_requested": entry.get("loop_count", 1),
                            "height": entry.get("height"),
                            "width": entry.get("width"),
                            "color": entry.get("color"),
                            "font size": entry.get("font size"),
                            "scroll speed": entry.get("scroll speed")
                        })
                    else:
                        print(f"Unknown entry type: {entry_type}")
                        self.show_index += 1
                        continue

                    # Wait for the entry to complete
                    self.show_entry_complete_event.clear()
                    completed = self.show_entry_complete_event.wait(timeout=60)  # adjust timeout as needed
                    if completed:
                        print(f"Entry {self.show_index+1} completed.")
                        self.show_index += 1
                    else:
                        print(f"Entry {self.show_index+1} timed out.")
                        self.show_index += 1

                # After finishing all entries, loop the show unless a new show is chosen or stop/shutdown is received
                if self.current_show and self.show_index >= len(self.current_show.get("entries", [])):
                    print(f"Show '{self.current_show.get('name')}' finished. Looping show...")
                    self.show_index = 0
            except Exception as e:
                print(f"Error in ShowController: {e}")

    def stop(self):
        self.shutdown_event.set()

