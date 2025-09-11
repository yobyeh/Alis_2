# menu_controller.py

import json
from pathlib import Path

class MenuController:

    def __init__(self):
        self.menu_path = Path("data/menu.json")
        self.menu_data = self.load_menu()
        self.screens = list(self.menu_data.get("screens", {}).keys())
        self.pointer_tracker = []
        self.current_screen_idx = 0
        self.current_item_idx = 0
        self.start_point_tracker()

    # 1 is the location of the pointer in the menu structure
    def start_point_tracker(self):

    def get_frame(self):
        pass

    def get_pointer_location(self):
        return self.current_screen_idx, self.current_item_idx

    def move_pointer(self, direction: str):

        match direction:
            case "UP":
               
            case "DOWN":
                
            case "SELECT":
                
            case "BACK":
                
            case _:
                print(f"Unknown direction: {direction}")

        # Set new pointer
        self.pointer_tracker[self.current_screen_idx][self.current_item_idx] = 1
        print(self.pointer_tracker)

    def load_menu(self):
        if self.menu_path.exists():
            with open(self.menu_path, "r") as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Menu file not found: {self.menu_path}")