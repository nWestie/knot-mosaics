#! /usr/bin/env python
import argparse
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from functools import partial
from multiprocessing import current_process
from pathlib import Path
import textwrap
import threading
from matplotlib import pyplot as plt
import mosaic_tools as mtool
from typing import Any
from time import sleep, time

# sage doesn't have type support ¯\_(ツ)_/¯
from sage.all import Link, SR  # type:ignore


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(help="mode to run in", required=True)
    parser.add_argument(
        '-i', '--images', help='Generate images', action='store_true')

    string = subs.add_parser("string", help="Parse a single string")
    string.add_argument('string', help='Determine knot type from string')
    string.set_defaults(func=handle_str)

    dir = subs.add_parser("dir",
                          help='parse mosiacs in dir corresponding to this ID')
    dir.add_argument('id', help='parse folder of mosaic lists')
    dir.set_defaults(func=handle_dirs)

    merge = subs.add_parser(
        'merge', help='merge result files with this ID string')
    merge.add_argument('id', help='folder name in output & data')
    merge.set_defaults(func=handle_merge)

    file = subs.add_parser('file', help="parse single file")
    file.add_argument('input_file', help="path of file to parse", type=Path)
    file.add_argument(
        'output_file', help="path to ouput results to", type=Path)
    file.set_defaults(func=handle_file)
    args = parser.parse_args()
    args.func(args)


def handle_dirs(args):
    inp_dir = Path(f"data/{args.id}")
    out_dir = Path(f"output/{args.id}_raw")
    run_catalog(inp_dir, out_dir)


def handle_merge(args):
    combine_results(args.merge)


def handle_str(args):
    mosaic_str = args.string
    knot = parse_mosaic(mosaic_str)
    if type(knot) is str:
        print(f"Bad Mosaic: {mosaic_str}")
        return

    if not knot or not knot.is_knot():  # type:ignore
        print("Mosaic is not a knot")
        return
        # knot = knot.simplify(exhaustive=True, height=3)
    knot = knot.simplify()  # type: ignore
    knotinfo = str(knot.get_knotinfo())
    polynomial = str(knot.homfly_polynomial())
    print(f"{mosaic_str} || {knotinfo} || {polynomial}")

    img_path = Path(f"output/other_img/{mosaic_str.strip()}.png")
    gen_png(mosaic_str, polynomial, knotinfo, img_path)


def handle_file(args):
    catalog_file(args.input_file, args.output_file)


@dataclass
class Knot_Result:
    mosaic_str: str
    tile_ct: int
    polynomial: str

    def to_str(self) -> str:
        return f"{self.mosaic_str}|{self.tile_ct}|{self.polynomial}"

    @classmethod
    def from_str(cls, str: str):
        parts = str.strip().split("|")
        return Knot_Result(parts[0], int(parts[1]), parts[2])


def run_catalog(inp_dir: Path, out_dir: Path):
    """Uses multiple processes to parse through a directory of mosaic files"""

    out_dir.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=6) as executor:
        i = 0

        # Thread to wait for user input without blocking main tasks
        stop_event = threading.Event()  # will be set by keypress thread

        def wait_for_key():
            input()
            print("stopping...", flush=True)
            stop_event.set()
        print("Press Enter to stop submitting new tasks...\n")
        threading.Thread(target=wait_for_key, daemon=True).start()

        max_queue = 8
        futures: dict[Future, int] = {}
        while not stop_event.is_set():
            # Printing status, consuming old results
            min_ind = min(futures.values() or (0,))
            done = [r for r in futures.keys() if r.done()]
            if done:
                print(f"Oldest running file: #{min_ind}", flush=True)
            for res in done:
                ind = futures.pop(res)
                exp = res.exception()
                if exp:
                    print(f"RESULT {ind} FAILS", flush=True)
                else:
                    print(f"Result {ind} done", flush=True)

            # Queueing new files
            if len(futures) < max_queue:
                in_path = inp_dir / f"pt{i}.txt"
                out_path = out_dir / f"pt{i}.txt"
                i += 1

                if out_path.is_file():
                    # TODO: this should maybe check for end_flag?
                    continue
                if not in_path.is_file():
                    break
                print(f"Queued {in_path}", flush=True)
                fut = executor.submit(
                    catalog_file, in_path, out_path)
                futures[fut] = i-1
            else:
                sleep(1)

        print("waiting for current workers to finish...", flush=True)
        [print(f"Working on: {i}, running={fut.running()}")
         for fut, i in futures.items()]
        executor.shutdown(wait=True, cancel_futures=True)
        print("fully shutdown now")
        # [print("res:", r.result()) for r in futures if not r.cancelled()]
    return


def combine_results(path_id: str):
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
            # yes, I'm re-running the ID/simplify steps. But the alternative is to run knotID on all the result files...
            knot = parse_mosaic(mosaic_str)
            if knot is None or type(knot) is str:
                print("ERR: should not be null knots in final results")
                break
            new_knot = knot.simplify()  # type: ignore
            if new_knot is not None:
                knot = new_knot

            knotid = str(knot.get_knotinfo(unique=False))  # type: ignore
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


def catalog_file(in_file: Path, out_file: Path) -> tuple[list[Knot_Result], int]:
    """Finds all unique knots """
    # list of knot IDs we found already mapped to their tile number
    knot_bank: dict[str, Knot_Result] = {}

    # keep track of how many we've parsed
    line_ct = 0
    # iterating over each line in each file in the dir
    print(f"Starting {in_file} on {current_process().name}", flush=True)
    start_t = time()
    bad_mosaics: list[str] = []
    links: list[str] = []
    with in_file.open("r") as f:
        for mosaic_str in f:
            mosaic_str = mosaic_str.strip()
            line_ct += 1

            knot = parse_mosaic(mosaic_str)
            # print(f"ID'd {line_ct}")

            if (type(knot) is str):  # rules out like 40k
                bad_mosaics.append(f"{mosaic_str}\n")
                continue
            if (knot is None):  # rules out like 40k
                links.append(f"{mosaic_str}\n")
                continue

            new_knot = knot.simplify()  # type: ignore # probably expensive?
            if new_knot:
                knot = new_knot
            # print(f"Simp {line_ct}")

            polynomial = str(knot.homfly_polynomial())  # type: ignore
            tile_ct = count_tiles(mosaic_str)

            prev_best = knot_bank.get(polynomial)  # rules out  40k
            # this is safe because of short-circuit 'or' eval
            if prev_best is None or tile_ct < prev_best.tile_ct:
                result: Knot_Result = Knot_Result(
                    mosaic_str, tile_ct, polynomial)
                knot_bank[polynomial] = result

    d_time = time()-start_t
    # with (win_proj / "bad_mosaics.txt").open('a') as file:
    #     file.writelines(bad_mosaics)
    if len(bad_mosaics):
        print(f"Bad Mosaics in {in_file}", flush=True)
    with out_file.open("w") as out:
        out.write("\n".join(r.to_str() for r in knot_bank.values()))
        out.write("END_RESULT")

    print(f"Parsed {line_ct:,} from {in_file} in {d_time:.0f}s" +
          f" ({line_ct/d_time:.0f} lines/s)", flush=True)
    return list(knot_bank.values()), line_ct


def parse_mosaic(mosaic_string) -> Link | str | None:
    """Parses mosaic, returning a valid knot, the string if it crashes, or none if it's an invalid knot"""
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
    loop_ct = 0
    while not_looped:
        loop_ct += 1
        if loop_ct > 10_000:
            # TODO: this is a nasty hack and shouldn't stay
            return mosaic_string

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


def count_tiles(mosaic: str):
    return len([tile for tile in mosaic if tile != '0'])


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
