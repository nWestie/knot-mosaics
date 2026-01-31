from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import font
from PIL import Image, ImageTk
import cylindrical

# ---- DOES NOT run well in WSL2 ----

tiles = cylindrical.load_tile_imgs()


def fetch_image(img_name: str) -> Image.Image:
    # Placeholder example
    # Replace this with your real implementation
    mat = cylindrical.string2matrix(img_name)
    return cylindrical.to_img(mat, tiles)

class ImageBrowser(tk.Tk):
    def __init__(self, image_names):
        super().__init__()

        self.title("Image Browser")
        self.geometry("900x600")

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
        img = fetch_image(img_name)

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

def launch(images: list[str]):
    ImageBrowser(images).mainloop()


if __name__ == "__main__":
    file = Path("./data/2.txt")
    mosaics = [line.strip() for line in file.open()]

    launch(mosaics)