import magic
from pathlib import Path
from PIL import Image
import h5py
import numpy as np


class MatrixConvert:
    def __init__(self, folder="uploaded/raw", width=16, height=16, fps=30, out_folder="uploaded/images", grb=False, preview_size=128):
        self.folder = Path(folder)
        self.width = width
        self.height = height
        self.fps = fps
        self.out_folder = Path(out_folder)
        self.out_folder.mkdir(parents=True, exist_ok=True)
        self.preview_folder = self.out_folder / "preview"
        self.preview_folder.mkdir(parents=True, exist_ok=True)
        self.grb = grb  # Flag to save as GRB
        self.preview_size = preview_size

    def convert_uploaded_files(self):
        for file in self.folder.iterdir():
            if file.is_file():
                filetype = magic.from_file(str(file), mime=True)
                print(f"File: {file.name}, Type: {filetype}")
                match filetype:
                    case "image/jpeg" | "image/png":
                        print(f"Processing image: {file.name}")
                        self.process_image(file)
                    case "image/gif":
                        print(f"Processing GIF: {file.name}")
                        # TODO: Add GIF processing here
                    case "video/mp4":
                        print(f"Processing MP4: {file.name}")
                        # TODO: Add MP4 processing here
                    case _:
                        print(f"Unknown type: {file.name}")

    def process_image(self, file):
        try:
            img = Image.open(file)
            img = img.convert("RGB")
            img = img.resize((self.width, self.height), Image.LANCZOS)
            matrix = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            for y in range(self.height):
                for x in range(self.width):
                    r, g, b = img.getpixel((x, y))
                    if self.grb:
                        matrix[y, x] = [g, r, b]  # GRB order
                    else:
                        matrix[y, x] = [r, g, b]  # RGB order
            print(f"Matrix for {file.name}:")
            print(matrix)
            self.save_matrix_h5(file.stem, matrix)
            self.save_image_preview(file.stem, img)
        except Exception as e:
            print(f"Error processing image {file.name}: {e}")

    def save_matrix_h5(self, name, matrix):
        out_path = self.out_folder / f"{name}.h5"
        with h5py.File(out_path, "w") as h5f:
            h5f.create_dataset("frames", data=matrix[np.newaxis, ...])  # shape: (1, height, width, 3)
            h5f.attrs["matrix_size"] = (self.height, self.width)
            h5f.attrs["num_frames"] = 1
            h5f.attrs["color_order"] = "GRB" if self.grb else "RGB"
        print(f"Saved matrix to {out_path}")

    def save_image_preview(self, name, img):
        preview_path = self.preview_folder / f"{name}.png"
        preview_img = img.resize((self.preview_size, self.preview_size), Image.NEAREST)
        preview_img.save(preview_path)
        print(f"Saved preview to {preview_path}")


def run_matrix_convert(grb=True, width=16, height=16, folder="uploaded/raw", out_folder="uploaded/images"):
    converter = MatrixConvert(grb=grb, width=width, height=height, folder=folder, out_folder=out_folder)
    converter.convert_uploaded_files()


# Example usage for direct run:
if __name__ == "__main__":
    run_matrix_convert(grb=True)