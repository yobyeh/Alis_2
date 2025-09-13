#screen_controller.py

from PIL import Image, ImageDraw, ImageFont

class ScreenController:

    def __init__(self, width, height):
        self.width = width
        self.height = height
        
    def draw_screen(self, screen, option):
        #based on what screen and what selection draw the screen
        img = Image.new("RGB", (self.width, self.height), (0,0,0)) # type: ignore
        draw = ImageDraw.Draw(img)

        # 3. Draw shapes
        draw.rectangle([20, 20, 180, 80], outline="black", fill="lightblue")
        draw.ellipse([50, 100, 150, 180], outline="green", fill="yellow")

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except IOError:
            font = ImageFont.load_default()

        draw.text((30, 30), "Hello, PIL!", fill="black", font=font)
        
        return img