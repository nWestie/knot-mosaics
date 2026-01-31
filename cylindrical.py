import argparse
import os
from PIL import Image, ImageDraw
from dataclasses import dataclass


def to_img(mosaic_tiles: list[int], tile_images) -> Image.Image:
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
        out_img.paste(tile_images[tile], (xind*tile_size, yind*tile_size))
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


def string2matrix(string: str) -> list[int]:
    """convert each char in the string to an int, 
    using hex conversion to properly convert 'a' to 11 """
    return [int(elem, base=16) for elem in string]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--images', help='Print image(s)', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',help='Determine knot type from string')

    args = parser.parse_args()

    tile_images = load_tile_imgs()
    mat = string2matrix(args.string)

if __name__ == "__main__":
    main()