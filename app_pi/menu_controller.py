# menu_controller.py

import json
from pathlib import Path
from screen_controller import ScreenController

class MenuController:

    def __init__(self, screen_controller):
        self.menu_path = Path("data/menu_data.json")
        self.menu_data = self.load_menu()
        self.screens = list(self.menu_data.get("screens", {}).keys())
        self.pointer_tracker = []
        self.start_point_tracker()
        self.change = 1
        self.screen_controller = screen_controller

    # 1 is the location of the pointer in the menu structure
    def start_point_tracker(self):
        #sereens array
        home_menu = []
        for screen in self.menu_data["home"]:
            home_menu.append(0)
        self.pointer_tracker.append(home_menu)
        for screen in self.menu_data["home"]:
            print(screen)
            curent_screen = []
            #options array
            for options in self.menu_data["home"][screen]:
                print("--", options)
                curent_screen.append(0)
            self.pointer_tracker.append(curent_screen)
        print(self.pointer_tracker)

    def start_menu(self):
        self.pointer_tracker[0][0] = 1
        print(self.pointer_tracker)

    def get_frame(self):
        self.change = 0
        screen_idx, option_idx = self.get_pointer_location()
        img = self.screen_controller.draw_screen(screen_idx, option_idx)
        return img

    def get_change(self):
        return self.change

    def get_pointer_location(self):
        screen_current = -1
        option_current = -1
        for screen in self.pointer_tracker:
            screen_current += 1
            for option in screen:
                option_current += 1
                if self.pointer_tracker[screen_current][option_current] == 1:
                    return screen_current, option_current
            option_current = -1
        print("pointer location error")
        return screen_current, option_current

    def move_pointer(self, direction: str):
        self.change = 1
        screen_current, option_current = self.get_pointer_location()
        self.pointer_tracker[screen_current][option_current] = 0
        match direction:
            case "UP":
                #if on the top flip to bottom
                if option_current == 0:
                    last_index = len(self.pointer_tracker[screen_current]) - 1
                    self.pointer_tracker[screen_current][last_index] = 1
                #if not move up one
                else:
                    self.pointer_tracker[screen_current][option_current - 1] = 1
            case "DOWN":
                #if on bottom flip to top
                last_index = len(self.pointer_tracker[screen_current]) - 1
                if option_current == last_index:
                    self.pointer_tracker[screen_current][0] = 1
                #if not move down one
                else:
                    self.pointer_tracker[screen_current][option_current + 1] = 1
            case "SELECT":
                #if main menu dive menu
                if screen_current == 0:
                    self.pointer_tracker[option_current + 1][0] = 1
                #if option run command
            case "BACK":
                self.pointer_tracker[0][0] = 1
            case _:
                print(f"Unknown direction: {direction}")

        # Set new pointer
        print(self.pointer_tracker)

    def load_menu(self):
        if self.menu_path.exists():
            with open(self.menu_path, "r") as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Menu file not found: {self.menu_path}")