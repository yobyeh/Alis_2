#screen_controller.py

from PIL import Image, ImageDraw, ImageFont

class ScreenController:

    def __init__(self, width, height):
        self.width = width
        self.height = height


    #x y x y 
    #recieves: current screen index, current option index, and menu data
    #
    #6 on screen options at 20pt
    #room for bottom indicator
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

        #header
        draw.rectangle([0, 0, 320, 30], outline=(8, 0, 158), fill=(8, 0, 158), width=1)
        title = "Alis"
        if screen != 0:
            pass
        draw.text((2, 4), title, fill="white", font=font)
        
        #options and values
        i = 0
        for option in data["home"]:
            draw.text((10, 40 + i * 30), option, fill="white", font=font)
            draw.text((250, 40 + i * 30), "Value", fill="white", font=font)
            i += 1

        #selection
        select_start = 35
        select_end   = 65
        draw.rectangle([1, select_start + selection * 30, self.height-1, select_end + selection * 30], outline=(0, 221, 255), fill=None, width=2)
        return img