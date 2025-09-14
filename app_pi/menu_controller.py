# menu_controller.py

#owns the buttons and pointer tracking
#owns the setting changes

import json
from pathlib import Path
from screen_controller import ScreenController

class MenuController:
    # current settings data, settings thread lock, settings changed thread event
    def __init__(self, screen_controller, current_settings, settings_lock, settings_changed):
        self.menu_path = Path("data/menu_data.json")
        self.menu_data = self.load_menu()
        self.screens = list(self.menu_data.get("screens", {}).keys())
        self.pointer_tracker = []
        self.start_point_tracker()
        #pointer has moved or setting has changed
        self.change = 1
        self.screen_controller = screen_controller
        self.current_settings = current_settings
        self.settings_lock = settings_lock
        self.settings_changed = settings_changed

    # 1 is the location of the pointer in the menu structure
    def start_point_tracker(self):
        #sereens array
        home_menu = []
        for screen in self.menu_data["home"]:
            home_menu.append(0)
        self.pointer_tracker.append(home_menu)
        for screen in self.menu_data["home"]:
            #print(screen)
            curent_screen = []
            #options array
            for options in self.menu_data["home"][screen]:
                #print("--", options)
                curent_screen.append(0)
            self.pointer_tracker.append(curent_screen)
        #print(self.pointer_tracker)

    def start_menu(self):
        self.pointer_tracker[0][0] = 1
        #print(self.pointer_tracker)

    def get_frame(self):
        self.change = 0
        screen_idx, option_idx = self.get_pointer_location()
        img = self.screen_controller.draw_screen(screen_idx, option_idx, self.menu_data)
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
                    #print("get pointer", screen_current, option_current)
                    return screen_current, option_current
            option_current = -1
        print("pointer location error")
        return screen_current, option_current

    def move_pointer(self, direction: str):
        self.change = 1
        screen_current, option_current = self.get_pointer_location()
        self.pointer_tracker[screen_current][option_current] = 0
        print(screen_current,option_current)
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
                # If main menu, dive into submenu
                if screen_current == 0:
                    self.pointer_tracker[option_current + 1][0] = 1
                # If already in submenu, stay or run command
                else:
                    self.pointer_tracker[screen_current][option_current] = 1
                    self.do_action(screen_current, option_current)
            case "BACK":
                self.pointer_tracker[0][0] = 1
            case _:
                print(f"Unknown direction: {direction}")

        #print(self.pointer_tracker)

    #change a setting
    #send an action message to the correct reciever
    #screen index, option index
    def do_action(self, screen_current, option_current):
        self.change = 1
        screen_list = ["home"] + list(self.menu_data["home"].keys())
        option_list = list(self.menu_data["home"][screen_list[screen_current]].keys())

        setting_data = self.menu_data["home"][screen_list[screen_current]][option_list[option_current]]
        action = setting_data.get("action")
        available_values = setting_data.get("options", [])
        setting_name = option_list[option_current]

        with self.settings_lock:
            if action == "value" and available_values:
                current_value = self.current_settings.get(setting_name)
                try:
                    idx = available_values.index(current_value)
                except ValueError:
                    idx = -1
                # Rotate to next value
                next_idx = (idx + 1) % len(available_values)
                self.current_settings[setting_name] = available_values[next_idx]
                self.settings_changed.set()
            else:
                # Handle other actions (e.g., save, reset)
                pass

    def load_menu(self):
        if self.menu_path.exists():
            with open(self.menu_path, "r") as f:
                return json.load(f)
        else:
            raise FileNotFoundError(f"Menu file not found: {self.menu_path}")