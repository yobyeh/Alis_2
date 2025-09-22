import magic
from pathlib import Path
from PIL import Image
import h5py
import numpy as np

#hard coded W H fps
class MatrixConvert:
    def __init__(self, folder="uploaded/raw", width=16, height=16, fps=30, grb=False, preview_size=128):
        self.folder = Path(folder)
        self.width = width
        self.height = height
        self.fps = fps
        self.image_out_folder = Path("uploaded/images")
        self.image_out_folder.mkdir(parents=True, exist_ok=True)
        self.image_preview_folder = self.image_out_folder / "preview"
        self.image_preview_folder.mkdir(parents=True, exist_ok=True)
        self.anim_out_folder = Path("uploaded/animations")
        self.anim_out_folder.mkdir(parents=True, exist_ok=True)
        self.anim_preview_folder = self.anim_out_folder / "preview"
        self.anim_preview_folder.mkdir(parents=True, exist_ok=True)
        self.color_order = grb
        self.preview_size = preview_size

    #convert from raw and delete after process
    def convert_uploaded_files(self):
        for file in self.folder.iterdir():
            if file.is_file():
                filetype = magic.from_file(str(file), mime=True)
                print(f"File: {file.name}, Type: {filetype}")
                match filetype:
                    case "image/jpeg" | "image/png":
                        print(f"Processing image: {file.name}")
                        self.process_image(file)
                        # Delete the raw file after processing
                        file.unlink()
                        print(f"Deleted raw file: {file}")
                    case "image/gif":
                        print(f"Processing GIF: {file.name}")
                        self.process_gif(file)
                        # Delete the raw file after processing
                        file.unlink()
                        print(f"Deleted raw file: {file}")
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
                    if self.color_order:
                        matrix[y, x] = [g, r, b]
                    else:
                        matrix[y, x] = [r, g, b]
            self.save_matrix_h5(file.stem, matrix[np.newaxis, ...], is_animation=False)
            self.save_image_preview(file.stem, img, is_animation=False)
        except Exception as e:
            print(f"Error processing image {file.name}: {e}")

    def process_gif(self, file):
        try:
            img = Image.open(file)
            frames = []
            frame_count = getattr(img, "n_frames", 1)
            for frame_idx in range(frame_count):
                img.seek(frame_idx)
                frame = img.convert("RGB").resize((self.width, self.height), Image.LANCZOS)
                matrix = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                for y in range(self.height):
                    for x in range(self.width):
                        r, g, b = frame.getpixel((x, y))
                        if self.color_order:
                            matrix[y, x] = [g, r, b]
                        else:
                            matrix[y, x] = [r, g, b]
                frames.append(matrix)
            frames_np = np.stack(frames)  # shape: (num_frames, height, width, 3)
            self.save_matrix_h5(file.stem, frames_np, is_animation=True)
            self.save_image_preview(file.stem, img, is_animation=True)
            print(f"Processed GIF: {file.name}, frames: {frame_count}")
        except Exception as e:
            print(f"Error processing GIF {file.name}: {e}")

    def save_matrix_h5(self, name, matrix, is_animation=False):
        if is_animation:
            out_path = self.anim_out_folder / f"{name}.h5"
        else:
            out_path = self.image_out_folder / f"{name}.h5"
        with h5py.File(out_path, "w") as h5f:
            h5f.create_dataset("frames", data=matrix)
            h5f.attrs["matrix_size"] = (self.height, self.width)
            h5f.attrs["num_frames"] = matrix.shape[0] if matrix.ndim == 4 else 1
            h5f.attrs["color_order"] = "GRB" if self.color_order else "RGB"
        print(f"Saved matrix to {out_path}")

    def save_image_preview(self, name, img, is_animation=False):
        if is_animation:
            preview_path = self.anim_preview_folder / f"{name}.png"
        else:
            preview_path = self.image_preview_folder / f"{name}.png"
        preview_img = img.resize((self.preview_size, self.preview_size), Image.NEAREST)
        preview_img.save(preview_path)
        print(f"Saved preview to {preview_path}")


def run_matrix_convert(grb=True, width=16, height=16, folder="uploaded/raw"):
    converter = MatrixConvert(grb=grb, width=width, height=height, folder=folder)
    converter.convert_uploaded_files()


# Example usage for direct run:
if __name__ == "__main__":
    run_matrix_convert(grb=True)