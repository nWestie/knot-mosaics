from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import font
from PIL import Image, ImageTk

# ---- DOES NOT run well in WSL2 (text doesn't scale) ----

def string2matrix(string: str) -> list[int]:
    """convert each char in the string to an int, 
    using hex conversion to properly convert 'a' to 11 """
    return [int(elem, base=16) for elem in string]


def to_img(mosaic_tiles: list[int]) -> Image.Image:
    tile_size = 64
    # border_size = 4
    # border_color = (196, 196, 196, 255)
    grid_size = int(len(mosaic_tiles)**0.5)
    assert grid_size**2 == len(mosaic_tiles),  "Mosaic must be square"

    pixel_size = (tile_size)*grid_size  # size of the finished img in pixels
    out_img = Image.new("RGB", (pixel_size, pixel_size), "white")

    xind = 0
    yind = 0
    for tile in mosaic_tiles:
        out_img.paste(tiles[tile], (xind*tile_size, yind*tile_size))
        # increment indexes to iterate over matrix
        xind = xind + 1
        if xind == grid_size:
            yind = yind + 1
            xind = 0

    return out_img


def load_tile_imgs():
    tile_images = {}
    for num in range(11):
        file_name = f"tiles/{num}.png"
        try:
            tile_images[num] = Image.open(file_name).convert("RGBA")
        except FileNotFoundError:
            print(f"Failed to load image {file_name}")
    return tile_images


class ImageBrowser(tk.Tk):
    def __init__(self, image_names, mosaic_type):
        super().__init__()

        self.title("Image Browser")
        self.geometry("900x600")

        self.image_names: list[str] = image_names
        self.current_index = 0
        self.tk_image = None  # keep reference!
        self.mosaic_type = mosaic_type
        self._build_ui()

        if self.image_names:
            self.show_image(0)

    def _build_ui(self):
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # ---- Left: Listbox + Scrollbar ----
        left_frame = ttk.Frame(paned, width=250)
        paned.add(left_frame, weight=1)

        scrollbar = ttk.Scrollbar(left_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(
            left_frame,
            yscrollcommand=scrollbar.set,
            activestyle="dotbox",
            font=("TKDefaultFont", 20)
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        for name in self.image_names:
            self.listbox.insert(tk.END, name)

        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # ---- Right: Image display ----
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=4)

        self.image_label = ttk.Label(right_frame, anchor="center")
        self.image_label.pack(fill=tk.BOTH, expand=True)

    def on_select(self, event):
        if not self.listbox.curselection():
            return
        index = self.listbox.curselection()[0]
        self.show_image(index)

    def show_image(self, index):
        index = max(0, min(index, len(self.image_names) - 1))
        self.listbox.selection_clear(self.current_index)
        self.current_index = index

        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)

        img_name = self.image_names[index]
        mat = self.mosaic_type.string2matrix(img_name)
        img = self.mosaic_type.to_img(mat, tiles)
        # Optional resize to fit window
        img = self._resize_to_label(img)

        self.tk_image = ImageTk.PhotoImage(img)
        self.image_label.configure(image=self.tk_image)

    def _resize_to_label(self, img):
        self.update_idletasks()
        w = self.image_label.winfo_width()
        h = self.image_label.winfo_height()
        if w > 1 and h > 1:
            img = img.copy()
            img.thumbnail((w, h), Image.LANCZOS)
        return img


def launch(images: list[str], mosaic_type):
    ImageBrowser(images, mosaic_type).mainloop()

tiles = load_tile_imgs()


if __name__ == "__main__":
    import cylindrical
    file = Path("./data/3_crosses.txt")
    mosaics = [line.strip() for line in file.open()]

    launch(mosaics, cylindrical)
