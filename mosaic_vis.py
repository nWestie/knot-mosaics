import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from tkinter.filedialog import askopenfilename
from matplotlib import pyplot as plt
from mosaic_util import *


def main():
    file = Path(askopenfilename(initialdir="./data"))
    if not file:
        exit()

    ImageBrowser.from_mosaic_file(file).mainloop()
    # ImageBrowser.from_strings(["000000212121989766663400","0021127a98883434"]).mainloop()


def gen_png(mosaic_str: str, id: str, img_path: Path):
    """Builds a PNG with metadata shown above/below mosaic"""
    matrix = string2matrix(mosaic_str)
    img = build_img(matrix)

    dpi: int = 300

    fig, ax = plt.subplots(
        nrows=2, figsize=(6, 7), gridspec_kw={"height_ratios": [6, 1]}, dpi=dpi
    )

    # ---- Image ----
    ax[0].imshow(img)
    ax[0].axis("off")
    ax[0].set_title(f"{mosaic_str}", fontsize=14, pad=10)

    # ---- Function text ----
    ax[1].axis("off")
    ax[1].text(
        0.5,
        0.5,
        f"ID: {id} Tile #: {count_tiles(mosaic_str)}",
        ha="center",
        va="center",
        fontsize=16,
        wrap=True,
    )

    plt.tight_layout()
    plt.savefig(img_path, bbox_inches="tight")
    plt.close(fig)

def build_img(mosaic_tiles: list[int]) -> Image.Image:
    """Builds a PIL image from a set of mosaic tiles"""
    if not hasattr(build_img, "tiles"):
        build_img.tiles = load_tile_imgs()

    tiles = build_img.tiles
    # border_size = 4
    # border_color = (196, 196, 196, 255)
    grid_size = len(mosaic_tiles) ** 0.5
    is_cubic = False
    if grid_size == int(grid_size):
        grid_size = int(grid_size)
        width = height = grid_size
    else:
        grid_size = (len(mosaic_tiles) / 6) ** 0.5
        grid_size = int(grid_size)
        width = grid_size * 3
        height = grid_size * 4
        is_cubic = True
    tile_size = tiles[0].width

    out_img = Image.new("RGB", (tile_size * width, tile_size * height), "white")

    for i, tile in enumerate(mosaic_tiles):
        x, y = index_to_xy(i, grid_size, is_cubic)
        out_img.paste(tiles[tile], (x * tile_size, y * tile_size))

    return out_img


def index_to_xy(index: int, size: int, is_cubic: bool) -> tuple[int, int]:
    if not is_cubic:
        col = index % size
        row = math.floor(index / size)
        return (col, row)
    cubic_len = size * size * 6
    # handle cubic
    if index < (cubic_len / 2):
        col = index % (size * 3)
        row = math.floor(index / (size * 3))
        return (col, row)

    index -= int(cubic_len / 2)
    col = index % size + size
    row = math.floor((index / size) + size)
    return (col, row)


def load_tile_imgs() -> dict[int, Image.Image]:
    tile_images = {}
    for file in Path("tiles/").glob("t*.png"):
        try:
            tile_images[int(file.stem[1:])] = Image.open(file).convert("RGBA")
        except FileNotFoundError:
            print(f"Failed to load image {file}")
            exit(-1)
    return tile_images


# ---- DOES NOT run well in WSL2 (text doesn't scale) ----
class ImageBrowser(tk.Tk):
    def __init__(self, image_names: list[str], getter):
        super().__init__()

        self.title("Image Browser")
        # self.geometry("900x600")
        try:
            self.state("zoomed")
        except:
            pass
        self.get_img = getter
        self.image_names: list[str] = image_names
        self.current_index = 0
        self.tk_image = None  # keep reference!
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
            font=("TKDefaultFont", 16),
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        for name in self.image_names:
            self.listbox.insert(tk.END, name)

        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        # ---- Right: Image display ----
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)

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
        img = self.get_img(img_name)
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
            img.thumbnail((w, h), Image.LANCZOS)  # type: ignore
        return img

    @classmethod
    def from_img_folder(cls, dir: Path):
        def getter(mosaic):
            return Image.open(dir / f"{mosaic}.png")

        mosaics = [p.stem for p in dir.iterdir()]
        return ImageBrowser(mosaics, getter)

    @classmethod
    def from_mosaic_file(cls, file: Path):
        with open(file) as f:
            mosaics = [l.strip() for l in f.readlines()]

        def getter(mosaic: str):
            return build_img(string2matrix(mosaic))

        return ImageBrowser(mosaics, getter)

    @classmethod
    def from_strings(cls, strs: list[str]):
        def getter(mosaic: str):
            return build_img(string2matrix(mosaic))

        return ImageBrowser(strs, getter)


if __name__ == "__main__":
    exit(main())
