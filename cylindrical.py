import argparse
from collections import namedtuple
from dataclasses import dataclass
from functools import partial
from multiprocessing import Pool
import os
from pathlib import Path
import textwrap
from matplotlib import pyplot as plt
import mosaic_tools as mtool
from typing import Any
from time import time

# sage doesn't have type support ¯\_(ツ)_/¯
from sage.all import Link, SR  # type:ignore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--images', help='Print image', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',
                        help='Determine knot type from string')
    parser.add_argument(
        '-d', '--directory', help='Create knot catalog from directory of mosaic lists')
    parser.add_argument(
        '-m', '--merge', help='merge result files with this ID string')
    args = parser.parse_args()

    if args.images:
        img = mtool.to_img(mtool.string2matrix(args.string))
        path = Path("output/other_img")/f"{args.string}.png"
        img.save(path)
        print(f"saved to {path}")
        return

    if args.string is not None:
        mosaic_str = args.string
        knot = identify_mosaic(mosaic_str)
        if not knot or not knot.is_knot():
            print("Mosaic is not a knot")
            return
        # knot = knot.simplify(exhaustive=True, height=3)
        knot = knot.simplify()
        knotinfo = str(knot.get_knotinfo())
        polynomial = str(knot.homfly_polynomial())
        print(f"{mosaic_str} || {knotinfo} || {polynomial}")

        img_path = Path(f"output/other_img/{mosaic_str.strip()}.png")
        gen_png(mosaic_str, polynomial, knotinfo, img_path)

    if args.directory is not None:
        inp_dir = Path(args.directory)
        out_dir = Path("output")/(inp_dir.stem+"_raw")

        catalog_raw(inp_dir, out_dir)
    if args.merge is not None:
        combine_results(args.merge)


@dataclass
class Knot_Result:
    mosaic_str: str
    polynomial: str


def catalog_raw(inp_dir: Path, out_dir: Path):

    t_start = time()

    # files = [inp_dir/f"pt{ind}.txt" for ind in range(400)]
    files = [f for f in inp_dir.iterdir() if f.is_file()]
    # filter out files which already have a calculated result
    files = [f for f in files if not (out_dir/f.name).is_file()]

    print(f"Parsing {len(files)} files...")
    with Pool(6, maxtasksperchild=4) as pool:
        pool.map(partial(catalog_file, out_dir=out_dir), files)
    dt = time()-t_start
    # print(f"{tot_ct} mosiacs parsed in {dt:.0f}s: {tot_ct/dt:.0f} moaics/sec")
    return


def combine_results(path_id:str):
    all_results: dict[str, str] = {}
    
    raw_results = Path(f"output/{path_id}_raw")
    for file in raw_results.iterdir():
        results, complete = load_result_file(file)
        if not complete:
            print(f"{file} is incomplete")
        
        for polynomial, mosaic in results.items():
            if polynomial not in all_results:
                all_results[polynomial] = mosaic

    print("writing file and images...")
    img_dir = Path(f"output/{path_id}_imgs")
    img_dir.mkdir(parents=True, exist_ok=True)
    out_file = Path(f"output/{path_id}_results.txt")
    with out_file.open("w") as out:
        for polynomial, mosaic_str in all_results.items():
            knot = identify_mosaic(mosaic_str)
            if knot is None:
                print("ERR: should not be null knots in final results")
                break
            new_knot = knot.simplify()
            if new_knot is not None:
                knot = new_knot
            
            knotid = str(knot.get_knotinfo(unique=False))
            polynomial = str(SR(polynomial))
            img_path = img_dir / (mosaic_str+".png")
            gen_png(mosaic_str, polynomial, knotid, img_path)
            print(f"saved {img_path}")
            out.write(
                f"{mosaic_str} || {knotid} || {polynomial}\n")


def load_result_file(file: Path) -> tuple[dict[str, str], bool]:
    results = {}
    with file.open("r") as inp:
        for line in inp:
            # If this line is not present, indicates an interruption during writing.
            if line.strip() == "END_RESULT":
                return results, True
            mosaic, polynomial = [p.strip() for p in line.split(",")]
            results[polynomial] = mosaic
    return results, False


def catalog_file(in_file: Path, out_dir: Path) -> tuple[list[Knot_Result], int]:
    """Finds all unique knots """
    # list of knot IDs we found already
    knot_list: list[str] = []
    results: list[Knot_Result] = []

    # keep track of how many we've parsed
    line_ct = 0
    # iterating over each line in each file in the dir
    print(f".. starting {in_file}")
    start_t = time()
    with in_file.open("r") as f:
        for mosaic_str in f:
            mosaic_str = mosaic_str.strip()
            line_ct += 1

            knot = identify_mosaic(mosaic_str)

            if (knot is None):  # rules out like 40k
                continue

            new_knot = knot.simplify()  # probably expensive?
            if new_knot:
                knot = new_knot

            polynomial = str(knot.homfly_polynomial())  # probably expensive

            if polynomial in knot_list:  # rules out  40k
                continue

            # runs ~10x
            knot_list.append(polynomial)

            # knotid = str(knot.get_knotinfo())
            results.append(Knot_Result(mosaic_str, polynomial))

    d_time = time()-start_t
    outfile = out_dir / in_file.name
    with outfile.open("w") as out:
        [out.write(f"{r.mosaic_str},{r.polynomial}\n") for r in results]
        out.write("END_RESULT")

    print(
        f"Parsed {line_ct:,} from {in_file} in {d_time:.0f}s ({line_ct/d_time:.0f} lines/s)")
    return results, line_ct


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
            return Link(pd_codes)


def count_crossings(mosaic: list[int]) -> int:
    return len([tile for tile in mosaic if tile in [9, 10]])


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
