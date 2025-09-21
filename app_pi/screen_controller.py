#screen_controller.py

from PIL import Image, ImageDraw, ImageFont
import threading

class ScreenController:

    def __init__(self, width, height, currnet_settings, settings_lock):
        self.width = width
        self.height = height
        self.settings_lock = settings_lock
        self.current_settings = currnet_settings
        self.font = self.get_font()

    def get_font(self):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except IOError:
            font = ImageFont.load_default()
        return font
    
    #240 x 320
    #x y x y 
    #recieves: current screen index, current option index, and menu data
    #6 on screen options at 20pt
    def draw_screen(self, screen, selection, menu_data):
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

        #footer
        draw.rectangle([0, 210, 320, 240], outline=(8, 0, 158), fill=(8, 0, 50), width=1)
        draw.text((10, 214), "Address:", fill="white", font=self.font)

        #options
        i = 0
        if screen == 0:
            for option in menu_data["home"]:
                draw.text((10, 40 + i * 30), option, fill="white", font=self.font)
                #draw.text((250, 40 + i * 30), "Value", fill="white", font=font)
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