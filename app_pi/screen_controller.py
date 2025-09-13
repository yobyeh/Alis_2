#screen_controller.py

from PIL import Image, ImageDraw, ImageFont

class ScreenController:

    def __init__(self, width, height):
        self.width = width
        self.height = height

    #240 x 320
    #x y x y 
    #recieves: current screen index, current option index, and menu data
    #6 on screen options at 20pt
    def draw_screen(self, screen, selection, data):
        # Swap width and height for portrait orientation
        #background
        img = Image.new("RGB", (self.height, self.width), (0,0,0))  # type: ignore
        draw = ImageDraw.Draw(img)
        #font
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except IOError:
            font = ImageFont.load_default()

        #build list of screens starting with home so index is correct
        screen_list = []
        screen_list.append("home")
        for option in data["home"]:
                screen_list.append(option)

        #header
        draw.rectangle([0, 0, 320, 30], outline=(8, 0, 158), fill=(8, 0, 158), width=1)
        title = "Alis"
        print("screen controler screen, selection", screen, selection)
        if screen != 0:
              title = screen_list[screen]
        draw.text((2, 4), title, fill="white", font=font)

        #footer
        draw.rectangle([0, 210, 320, 240], outline=(8, 0, 158), fill=(8, 0, 50), width=1)
        draw.text((10, 214), "Address:", fill="white", font=font)

        #options
        i = 0
        if screen == 0:
            for option in data["home"]:
                draw.text((10, 40 + i * 30), option, fill="white", font=font)
                #draw.text((250, 40 + i * 30), "Value", fill="white", font=font)
                i += 1
        else:
            current_screen = screen_list[screen]
            i = 0
            for option in data["home"][current_screen]:
                 draw.text((10, 40 + i * 30), option, fill="white", font=font)
                 i += 1


        #selection
        select_start = 35
        select_end   = 65
        draw.rectangle([1, select_start + selection * 30, self.height-1, select_end + selection * 30], outline=(0, 221, 255), fill=None, width=2)
        return img