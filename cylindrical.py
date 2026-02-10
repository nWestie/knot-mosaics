import argparse
import os
from pathlib import Path
import textwrap
from PIL import Image, ImageDraw
from matplotlib import pyplot as plt
from dataclasses import dataclass
import mosaic_tools as mtool
from typing import Any
# sage doesn't have type support ¯\_(ツ)_/¯
from sage.all import Link, SR  # type: ignore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--images', help='Print image(s)', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',
                        help='Determine knot type from string')
    parser.add_argument(
        '-d', '--directory', help='Create knot catalog from directory of mosaic lists')
    args = parser.parse_args()

    if args.string is not None:
        mosaic_str = args.string
        knot = identify_mosaic(mosaic_str)
        if not knot:
            return
        knotinfo = str(knot.get_knotinfo())
        polynomial = str(SR(knot.homfly_polynomial()))
        print(f"{mosaic_str} || {knotinfo} || {polynomial}")

        if args.images:
            img_path = Path(f"output/other_img/{mosaic_str.strip()}.png")
            gen_png(mosaic_str, polynomial, knotinfo, img_path)

    if args.directory is not None:
        inp = Path(args.directory)
        out_file = Path("output")/(inp.stem+".txt")

        catalog(inp, out_file)


def catalog(inp_dir: Path, out_file: Path):
    knot_list: list[str] = []

    img_dir = out_file.parent / (out_file.stem+"_imgs")
    img_dir.mkdir(parents=True, exist_ok=True)

    def lines():
        for file in inp_dir.iterdir():
            if not file.is_file():
                pass
            for line in file.open():
                yield line.strip()

    # iterating over each line in each file in the dir
    with out_file.open("w") as out_stream:
        for mosaic_str in lines():
            knot = identify_mosaic(mosaic_str)
            if not knot:
                continue

            knotid = str(knot.get_knotinfo())

            if knotid in knot_list:
                continue
            knot_list.append(knotid)

            polynomial = str(SR(knot.homfly_polynomial()))
            out_stream.write(f"{mosaic_str} || {knotid} || {polynomial}")
            out_stream.flush()
            print(f"Found {knotid}")

            img_path = img_dir / (mosaic_str+".png")
            gen_png(mosaic_str, polynomial, knotid, img_path)


def identify_mosaic(mosaic_string) -> Link | None:
    size = int(len(mosaic_string)**(0.5))
    # ASK: why initialize to 10? isn't this a crossing?
    mosaic = [[10]*(size**2)]
    mosaic.append([0]*(size**2))
    satisfied: list[list[bool]] = [[False]*(size ** 2)]
    # THIS CHANGED - used to be mirred between both layers
    satisfied.append([False]*(size**2))
    crossing_strands = [
        [[0]*4 for _ in range((size ** 2))] for _ in range(2)]

    made_connections = [[[] for _ in range(size ** 2)] for _ in range(2)]
    crossing_indices = []
    pd_codes: list[list[int]] = []
    # Layer 0 "front", 1 holds hidden crossings
    tile_index = layer = face = 0
    strand_number = 1

    for i, char in enumerate(mosaic_string.strip()):
        num = int(char, base=16)
        mosaic[0][i] = num
        satisfied[0][i] = (num == 0)

    # move index to start on the first non-zero tile
    while mosaic[0][tile_index] == 0:
        tile_index += 1

    for i in range(size):
        # iterating through left side
        if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1, 4, 5):
            for j in range(size):
                # ASK: adding 5 to the whole row? Other one adds 6 if it is on top edge?
                mosaic[1][i*size + j] += 5
        # iterating through top row edge?
        if mosaic[0][i] > 6 or mosaic[0][i] in (3, 4, 6):
            for j in range(size):
                mosaic[1][(j+1)*size - (i+1)] += 6

    # curr_tile always starts at a non-zero tile, so this never errs
    curr_tile = mosaic[layer][tile_index]
    face = valid_connections[curr_tile][0][0]  # type: ignore
    not_looped = True
    while not_looped:
        curr_tile = mosaic[layer][tile_index]
        for conn in valid_connections[curr_tile]:
            if conn[0] == face:
                if conn in made_connections[layer][tile_index]:
                    not_looped = False
                    break  # break for & while

                made_connections[layer][tile_index].append(conn)
                if ((len(made_connections[layer][tile_index]) == 1) and curr_tile < 7) or (len(made_connections[layer][tile_index]) == 2):
                    # If the tile has all the connections it needs, we're done
                    satisfied[layer][tile_index] = True

                # Crossing logic
                if curr_tile > 8:  # if it is a crossing
                    if satisfied[layer][tile_index]:
                        crossing_indices.append([layer, tile_index])
                    crossing_strands[layer][tile_index][face] = strand_number
                    strand_number += 1
                    crossing_strands[layer][tile_index][(
                        face + 2) % 4] = strand_number
                else:
                    face = (conn[1] + 2) % 4

                # Go to next tile
                if face == 0:  # left
                    if tile_index % size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size*((tile_index//size) + 1) - 1
                    else:
                        tile_index -= 1
                elif face == 1:  # down
                    if (tile_index // size) == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size**2 - (tile_index % size + 1)
                        face = 3
                    else:
                        tile_index += size
                elif face == 2:  # right
                    if tile_index % size == size - 1:
                        layer = (layer + 1) % 2
                        tile_index = size*(tile_index // size)
                    else:
                        tile_index += 1
                elif face == 3:  # up
                    if tile_index // size == 0:
                        layer = (layer + 1) % 2
                        tile_index = size - (tile_index + 1)
                        face = 1
                    else:
                        tile_index -= size
                break
    # This is pretty much a completely different phase of the func
    # assume it's the part that actually figures out what knot it is?
    if all(satisfied[0]):
        if len(crossing_indices) < 3:
            # Must be the unknot if there's less than 3 crossings
            homf = 1
        else:
            for i0, i1 in crossing_indices:
                if mosaic[i0][i1] == 9:
                    if (0, 2) in made_connections[i0][i1]:
                        pd_codes.append(
                            crossing_strands[i0][i1])
                    else:
                        # Rotated by 2
                        pd_codes.append(
                            crossing_strands[i0][i1][2:] + crossing_strands[i0][i1][:2])
                else:
                    if (1, 3) in made_connections[i0][i1]:
                        pd_codes.append(
                            crossing_strands[i0][i1][1:] + crossing_strands[i0][i1][:1])
                    else:
                        pd_codes.append(
                            crossing_strands[i0][i1][3:] + crossing_strands[i0][i1][:3])
            for l in range(len(pd_codes[-1])):
                if pd_codes[-1][l] == strand_number:
                    pd_codes[-1][l] = 1
                    break
            return Link(pd_codes).remove_loops()


def count_crossings(mosaic: list[int]) -> int:
    return len([tile for tile in mosaic if tile in [10, 11]])


def gen_png(mosaic_str: str, homfly: str, id: str, img_path: Path):

    matrix = mtool.string2matrix(mosaic_str)
    img = mtool.to_img(matrix)

    dpi: int = 300
    func_text = textwrap.fill(f"${homfly}$", width=60)

    fig, ax = plt.subplots(nrows=2, figsize=(6, 7), gridspec_kw={
                           "height_ratios": [6, 1]}, dpi=dpi)

    # ---- Image ----
    ax[0].imshow(img)
    ax[0].axis("off")
    ax[0].set_title(f"{mosaic_str}", fontsize=14, pad=10)

    # ---- Function text ----
    ax[1].axis("off")
    ax[1].text(0.5, 0.75, func_text, ha="center", va="center",
               fontsize=16, wrap=True,)
    ax[1].text(0.5, 0.25, f"ID: {id} Cross count: {count_crossings(matrix)}", ha="center", va="center",
               fontsize=16, wrap=True,)

    plt.tight_layout()
    plt.savefig(img_path, bbox_inches="tight")
    plt.close(fig)


valid_connections = (
    (()),
    ((2, 3), (3, 2)),
    ((0, 3), (3, 0)),
    ((0, 1), (1, 0)),
    ((2, 1), (1, 2)),
    ((2, 0), (0, 2)),
    ((1, 3), (3, 1)),
    ((2, 3), (3, 2), (1, 0), (0, 1)),
    ((0, 3), (3, 0), (2, 1), (1, 2)),
    ((0, 2), (1, 3), (2, 0), (3, 1)),
    ((0, 2), (1, 3), (2, 0), (3, 1)),
    ((0, 2), (1, 3), (2, 0), (3, 1))
)


if __name__ == "__main__":
    main()
