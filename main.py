#! /usr/bin/env python
import argparse
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import current_process
from pathlib import Path
import textwrap
import threading
from time import sleep, time
import mosaics as m
import mosaic_vis as mvis

# sage doesn't have type support ¯\_(ツ)_/¯
from sage.all import Link, SR  # type:ignore


output_dir = Path(f"output/")
def mosaic_dir(id): return Path(f"data/{id}")
def results_dir(id): return Path(f"data/{id}_res")
def img_dir(id): return output_dir / f"{id}_imgs"


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
    dir.add_argument('-m', '--merge-also', action='store_true',
                     help='also run merge after parsing')
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
    id = args.id
    run_catalog(mosaic_dir(id), results_dir(id),redo=True)
    if args.merge_also:
        print("Merging...", flush=True)
        handle_merge(args)


def handle_merge(args):
    combine_results(args.id)


def handle_file(args):
    catalog_file(args.input_file, args.output_file)


def run_catalog(inp_dir: Path, out_dir: Path, redo: bool = False):
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
        key_thread = threading.Thread(target=wait_for_key, daemon=True)
        key_thread.start()

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

                if out_path.is_file() and not redo:
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
    """ Takes a dir of knot results and combines them, selecting the lowest tile # for each knot"""
    # maps polynomial to knot result
    all_results: dict[str, Knot_Result] = {}

    # merge results, keeping lowest tile number
    results_folder = results_dir(path_id)
    for file in results_folder.iterdir():
        results, complete = load_result_file(file)
        if not complete:
            print(f"{file} is incomplete")
        for r in results:
            prev_best = all_results.get(r.polynomial)
            # this is safe because of short-circuit 'or' eval
            if prev_best is None or r.tile_ct < prev_best.tile_ct:
                all_results[r.polynomial] = r

    # generate images
    print("writing file and images...")
    imgs = img_dir(path_id)
    imgs.mkdir(parents=True, exist_ok=True)
    # tuples of (knotID, polynomial)
    knot_ids: list[tuple[str, str]] = []
    for polynomial, res in all_results.items():
        # yes, I'm re-running the ID/simplify steps.
        # But the alternative is to run knotID on all the result files...
        knot = m.parse_mosaic(res.mosaic_str)
        if knot is None or type(knot) is str:
            print("ERR: should not be null knots in final results")
            break
        new_knot = knot.simplify()  # type: ignore
        if new_knot is not None:
            knot = new_knot

        knotid = str(knot.get_knotinfo(unique=False))  # type: ignore
        for s in ["KnotInfo", '[', ']', "'"]:
            knotid = knotid.replace(s, "")
        knot_ids.append((knotid, polynomial))
        img_path = imgs / (f"{knotid}__{res.mosaic_str}.png")
        mvis.gen_png(res.mosaic_str, knotid, img_path)
        print(f"saved {img_path}")
    # generate output file
    knot_ids.sort(key=lambda k: k[0])
    out_file = output_dir / f"{path_id}_results.txt"
    with out_file.open("w") as out:
        for id, poly in knot_ids:
            res = all_results[poly]
            out.write(f"{id} : {res.mosaic_str} : {str(SR(poly))}\n")


def load_result_file(file: Path) -> tuple[list[Knot_Result], bool]:
    """Extracts knot results from file. Returns true if file contains the correct end-indicator"""
    results: list[Knot_Result] = []
    with file.open("r") as inp:
        for line in inp:
            # If this line is not present, indicates an interruption during writing.
            line = line.strip()
            if line == "END_RESULT":
                return results, True
            results.append(Knot_Result.from_str(line))
    return results, False


def catalog_file(in_file: Path, out_file: Path) -> tuple[list[Knot_Result], int]:
    """Finds all unique knots """
    # maps polynomial to tile number/mosaic
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

            knot = m.parse_mosaic(mosaic_str)
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
            tile_ct = m.count_tiles(mosaic_str)

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
        lines = [r.to_str() for r in knot_bank.values()]
        out.write("\n".join(lines))
        out.write("\nEND_RESULT")

    print(f"Parsed {line_ct:,} from {in_file} in {d_time:.0f}s" +
          f" ({line_ct/d_time:.0f} lines/s)", flush=True)
    return list(knot_bank.values()), line_ct


def handle_str(args):
    mosaic_str: str = args.string
    mosaic = m.NormMosaic.build_cylindrical(mosaic_str)
    knot = m.traverse_mosaic(mosaic)
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
    mvis.gen_png(mosaic_str, knotinfo, img_path)


if __name__ == "__main__":
    main()
