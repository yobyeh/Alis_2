#screen_controller.py

from PIL import Image, ImageDraw, ImageFont
import threading
import os
import math

class ScreenController:

    def __init__(self, width, height, currnet_settings, settings_lock):
        self.width = width
        self.height = height
        self.settings_lock = settings_lock
        self.current_settings = currnet_settings
        self.font = self.get_font()
        self.address = ""
        self.signal: int | None = 0
        self.connected = False
        self.signal_images = []
        self.load_wifi_images()
        self.lowercase = "abcdefghijklmnopqrstuvwxyz"
        self.uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.numbers = "1234567890"
        self.symbols = "@!#$%^&*()_-+=[]{}|:;\"',.<>/?~`"
        self.text_center_x = 100
        self.text_center_y = 100
        #space and enter

    def get_font(self):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        return font

    def get_asset_image(self, filename):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        asset_path = os.path.join(base_dir, "assets", filename)
        print(f"Loading asset image: {asset_path}")
        return Image.open(asset_path) 
    
    def load_wifi_images(self):
        print("Loading WiFi signal images...")
        self.signal_images.append(self.get_asset_image("no_signal.png"))
        self.signal_images.append(self.get_asset_image("low_signal.png"))
        self.signal_images.append(self.get_asset_image("med_signal.png"))
        self.signal_images.append(self.get_asset_image("high_signal.png"))
        print(f"Loaded {len(self.signal_images)} WiFi images.")
        print(f"Signal images loaded: {len(self.signal_images)}")

    def get_arc_positions(center_x, center_y, radius, num_letters, start_angle=0, end_angle=180):
        """
        Returns a list of (x, y, angle) positions for letters arranged in an arc.
        Angles are in degrees. 0 degrees is to the right, 90 is up.
        """
        positions = []
        if num_letters == 1:
            angles = [math.radians((start_angle + end_angle) / 2)]
        else:
            angles = [
                math.radians(start_angle + i * (end_angle - start_angle) / (num_letters - 1))
                for i in range(num_letters)
            ]
        for angle in angles:
            x = center_x + radius * math.cos(angle)
            y = center_y - radius * math.sin(angle)
            positions.append((x, y, math.degrees(angle)))
        return positions

    def draw_rotated_text(img, text, position, angle, font, fill):
        # Create a transparent image for the text
        text_img = Image.new('RGBA', img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(text_img)
        w, h = draw.textsize(text, font=font)
        text_pos = (position[0] - w // 2, position[1] - h // 2)
        draw.text(text_pos, text, font=font, fill=fill)
        # Rotate around the center of the text
        rotated = text_img.rotate(angle, center=position, resample=Image.BICUBIC)
        # Composite onto base image
        img.paste(rotated, (0, 0), rotated)

    #240 x 320
    #x y x y 
    #recieves: current screen index, current option index, and menu data
    #6 on screen options at 20pt
    def draw_screen(self, screen, selection, menu_data, shows_list):
        print(f"Drawing screen: screen={screen}, selection={selection}, address={self.address}, signal={self.signal}")
        # Swap width and height for portrait orientation
        #background
        img = Image.new("RGB", (self.height, self.width), (0,0,0))  # type: ignore
        draw = ImageDraw.Draw(img)

        #build list of screens starting with home so index is correct
        screen_list = []
        screen_list.append("home")
        for option in menu_data["home"]:
                screen_list.append(option)

        #header
        draw.rectangle([0, 0, 320, 30], outline=(8, 0, 158), fill=(8, 0, 158), width=1)
        title = "Alis"
        #print("screen controler screen, selection", screen, selection)
        if screen != 0:
              title = screen_list[screen]
        draw.text((2, 4), title, fill="white", font=self.font)
        
        #wifi signal
        print(f"Signal value: {self.signal}")
        if self.signal_images and self.signal is not None:
            # Clamp signal value to valid range
            idx = self.rssi_to_signal_index(self.signal)
            print(f"WiFi image index: {idx}")
            wifi_img = self.signal_images[idx]
            # Shrink image by half
            w, h = wifi_img.size
            wifi_img_small = wifi_img.resize((w // 2, h // 2), Image.LANCZOS)
            img.paste(wifi_img_small, (310 - w // 3, 4), wifi_img_small)  # Adjust position as needed
        else:
            print("No WiFi images loaded or signal is None.")

        #footer
        draw.rectangle([0, 210, 320, 240], outline=(8, 0, 158), fill=(8, 0, 50), width=1)
        draw.text((10, 214), f"http:// {self.address}:8000", fill="white", font=self.font)

        #options
        i = 0
        if screen == 0:
            for option in menu_data["home"]:
                draw.text((10, 40 + i * 30), option, fill="white", font=self.font)
                i += 1
        elif screen == 1:
                for name in shows_list:
                    draw.text((10, 40 + i * 30), name, fill="white", font=self.font)
                    i += 1
        else:
            current_screen = screen_list[screen]
            i = 0
            for option in menu_data["home"][current_screen]:
                 draw.text((10, 40 + i * 30), option, fill="white", font=self.font)
                 i += 1

        #values settings
        if screen_list[screen] == "Settings":
            self.settings_lock.acquire()
            i = 0
            for key, value in self.current_settings.items():
                #-1 is no default value
                if value != -1:
                    draw.text((250, 40 + i * 30), str(value), fill="white", font=self.font)
                i += 1
            self.settings_lock.release()
        
        #values led config
        if screen_list[screen] == "LED Config":
            self.settings_lock.acquire()
            i = 0
            for key, value in self.current_settings.items():
                #-1 is no default value
                if value != -1:
                    draw.text((250, 40 + i * 30), str(value), fill="white", font=self.font)
                i += 1
            self.settings_lock.release()

        #selection
        select_start = 35
        select_end   = 65
        draw.rectangle([1, select_start + selection * 30, self.height-1, select_end + selection * 30], outline=(0, 221, 255), fill=None, width=2)
        return img

    def clear_screen(self):
        """Return a blank (black) image for clearing the display."""
        return Image.new("RGB", (self.height, self.width), (0,0,0))  # type: ignore

    def rssi_to_signal_index(self, rssi):
        # Example thresholds, adjust as needed
        if rssi is None:
            return 0  # No signal
        if rssi > -60:
            return 3  # High
        elif rssi > -70:
            return 2  # Medium
        elif rssi > -80:
            return 1  # Low
        else:
            return 0  # No signal