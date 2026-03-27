#! /usr/bin/env python
import argparse
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import current_process
from pathlib import Path
import threading
from time import sleep, time
from typing import Callable
import mosaics as M
import mosaic_vis as mvis
from mosaic_util import *
from sage_funcs import make_knot

output_dir = Path(f"output/")


def mosaic_dir(type: str, size: int, cubic_type: str | None = None) -> Path:
    # get the input folder of mosaics
    path = Path(f"data/{size}_{type}")
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


def results_dir(type: str, cubic_type: str | None = None) -> Path:
    # get the output folder of intermediate results
    path = Path(f"data/{type}_res")
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


def img_dir(type: str, cubic_type: str | None = None) -> Path:
    # get the output folder for images
    path = output_dir / f"{type}_imgs"
    if cubic_type and type == "cubic":
        path /= cubic_type
    return path


@dataclass
class KnotResult:
    """Intermediate format for knot results"""

    size: int
    mosaic_str: str
    tile_ct: int
    polynomial: str

    def to_str(self) -> str:
        return f"{self.size}|{self.mosaic_str}|{self.tile_ct}|{self.polynomial}"

    @classmethod
    def from_str(cls, str: str):
        parts = str.strip().split("|")
        return KnotResult(
            int(parts[0]), parts[1].strip(), int(parts[2]), parts[3].strip()
        )

    def better_than(self, other: "KnotResult|None") -> bool:
        """Returns True if self is the preferred result over other"""
        # Some result preferred to none
        if other is None:
            return True
        # Smaller mosaic is preferred
        if self.size != other.size:
            return self.size < other.size
        # lower tile number is preferred
        if self.tile_ct != other.tile_ct:
            return self.tile_ct < other.tile_ct
        # lower indexes preffered
        return int(self.mosaic_str, 16) < int(other.mosaic_str, 16)
        # TODO: Implement edge connections metric?
        # fewer edge connections preferred. Would be super annoying with only results


def main():
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(help="mode to run in", required=True)
    parser.add_argument("-i", "--images", help="Generate images", action="store_true")

    string = subs.add_parser("string", help="Parse a single string")
    string.add_argument("string", help="Determine knot type from string")
    string.add_argument("type", choices=M.parser_types.keys(), help="type of mosaic")
    string.set_defaults(func=handle_str)

    parse = subs.add_parser(
        "parse", help="parse mosiacs in dir corresponding to this ID"
    )
    parse.add_argument("size", type=int, help="mosaic size")
    parse.add_argument("type", choices=M.parser_types.keys(), help="type of mosaic")
    parse.add_argument(
        "--keep-existing",
        action="store_true",
        help="skip inputs that have existing results",
    )
    parse.add_argument(
        "-c",
        "--cubic-version",
        help="Type of cubic to pull results from, must match the folder path",
        type=str,
    )
    parse.add_argument(
        "-x",
        "--no-clean-exit",
        help="Don't run the watcher that allows clean partial exits. For scripting",
        action="store_true",
    )
    parse.set_defaults(func=run_catalog)

    merge = subs.add_parser("merge", help="merge result files with this ID string")
    merge.add_argument(
        "type", choices=M.parser_types.keys(), help="folder name in output & data"
    )
    merge.add_argument(
        "-c",
        "--cubic-version",
        help="Type of cubic to pull results from, must match the folder path",
        type=str,
    )
    merge.set_defaults(func=combine_results)

    file = subs.add_parser("file", help="parse single file")
    file.add_argument("input_file", help="path of file to parse", type=Path)
    file.add_argument("output_file", help="path to ouput results to", type=Path)
    file.add_argument("type", help="type of mosaic", type=str)
    file.set_defaults(func=handle_file)
    args = parser.parse_args()
    args.func(args)


def handle_file(args):
    # raise NotImplementedError("Implement for multi-type input")
    catalog_file(args.input_file, args.output_file, M.parser_types[args.type])


def run_catalog(args):
    """Uses multiple processes to parse through a directory of mosaic files"""
    [type, size, redo] = [args.type, args.size, not args.keep_existing]
    builder: Callable[[str], M.NormMosaic] = M.parser_types[type]
    inp_dir = mosaic_dir(type, size, args.cubic_version)
    out_dir = results_dir(type, args.cubic_version)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Thread to wait for user input without blocking main tasks
    stop_event = threading.Event()  # will be set by keypress thread
    if not args.no_clean_exit:

        def wait_for_key():
            input()
            print("stopping...", flush=True)
            stop_event.set()

        print("Press Enter to stop submitting new tasks...\n")
        key_thread = threading.Thread(target=wait_for_key, daemon=True)
        key_thread.start()

    i = 0
    max_queue = 8
    futures: dict[Future, int] = {}
    # spawning workers to parse files
    with ProcessPoolExecutor(max_workers=6) as executor:
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
                in_path = inp_dir / f"pt{i:04}.txt"
                out_path = out_dir / f"{size}_pt{i:04}.txt"
                i += 1
                # if output is already generated:
                if out_path.is_file() and not redo:
                    continue
                # if we're done all the files in the folder, exit
                if not in_path.is_file():
                    break
                print(f"Queued {in_path}", flush=True)
                fut = executor.submit(catalog_file, in_path, out_path, builder)
                futures[fut] = i - 1
            else:
                sleep(1)

        print("waiting for current workers to finish...", flush=True)
        [
            print(f"Working on: {i}, running={fut.running()}")
            for fut, i in futures.items()
        ]
        executor.shutdown(wait=True, cancel_futures=True)
        print("fully shutdown now")


def combine_results(args):
    """Takes a dir of knot results and combines them, selecting the lowest tile # for each knot"""

    mosaic_type = args.type
    builder = M.parser_types[args.type]
    # maps polynomial to knot result
    all_results: dict[str, KnotResult] = {}

    # merge results, keeping lowest tile number
    results_folder = results_dir(mosaic_type, args.cubic_version)
    if not results_folder.is_dir() or len(list(results_folder.iterdir())) == 0:
        print(f"ERR: no results to merge for {results_folder}")
        return
    
    for file in results_folder.iterdir():
        results, complete = load_result_file(file)
        if not complete:
            print(f"{file} is incomplete")
        for res in results:
            prev_best = all_results.get(res.polynomial)
            # this is safe because of short-circuit 'or' eval
            if res.better_than(prev_best):
                all_results[res.polynomial] = res

    # generate images
    print("writing file and images...")
    imgs = img_dir(mosaic_type, args.cubic_version)
    if imgs.exists():
        [f.unlink() for f in imgs.iterdir()]
    else:
        imgs.mkdir(parents=True)
    # tuples of (knotID, polynomial)
    knot_ids: list[tuple[str, KnotResult]] = []
    for polynomial, res in all_results.items():
        # yes, I'm re-running the ID/simplify steps.
        # But the alternative is to run knotID on all the result files...
        mosaic = builder(res.mosaic_str)
        knot = M.traverse_mosaic(mosaic, prune_unknots=False)
        if type(knot) is M.NotAKnot:
            print(f"ERR: Not a Knot({type(knot)}): {res.mosaic_str}")
            break
        knot = make_knot(knot)  # type:ignore
        new_knot = knot.simplify()
        if new_knot is not None:
            knot = new_knot
        # this can be quite slow for some knots
        knotid = str(knot.get_knotinfo(unique=False))  # type: ignore
        # cleaning up the KnotInfo output
        for s in ["KnotInfo", "[", "]", "'"]:
            knotid = knotid.replace(s, "")
        img_path = imgs / (f"{res.size}-{knotid}-{res.mosaic_str}.png")
        mvis.gen_png(mosaic, res.mosaic_str, knotid, img_path)
        print(f"saved: {img_path}")

        knot_ids.append((knotid, res))

    # generate output file
    knot_ids.sort(key=lambda k: k[0])
    padding = max(len(k) for k, _ in knot_ids) + 1
    out_file = output_dir / f"{mosaic_type}_results.txt"
    with out_file.open("w") as out:
        for id, res in knot_ids:
            out.write(f"{id.ljust(padding)}|{res.to_str()}\n")


def load_result_file(file: Path) -> tuple[list[KnotResult], bool]:
    """Extracts knot results from file. Returns true if file contains the correct end-indicator"""
    results: list[KnotResult] = []
    with file.open("r") as inp:
        for line in inp:
            # If this line is not present, indicates an interruption during writing.
            line = line.strip()
            if line == "END_RESULT":
                return results, True
            if line:
                results.append(KnotResult.from_str(line))
    return results, False


def catalog_file(
    in_file: Path, out_file: Path, builder: Callable
) -> tuple[list[KnotResult], int]:
    """Finds all unique knots"""
    # maps polynomial to tile number/mosaic
    knot_bank: dict[str, KnotResult] = {}

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

            mosaic: M.NormMosaic = builder(mosaic_str)
            knot = M.traverse_mosaic(mosaic, prune_unknots=False)
            if type(knot) is M.NotAKnot:
                match knot:
                    case M.NotAKnot.BAD_CONNECTIONS:
                        bad_mosaics.append(f"{str(knot)}, {mosaic_str}\n")
                continue
            knot = make_knot(knot)  # type:ignore
            new_knot = knot.simplify()  # type: ignore # probably expensive?
            if new_knot:
                knot = new_knot

            polynomial = str(knot.homfly_polynomial())  # type: ignore
            tile_ct = M.count_tiles(mosaic_str)

            prev_best = knot_bank.get(polynomial)
            # this is safe because of short-circuit 'or' eval
            result: KnotResult = KnotResult(
                mosaic.nominal_size, mosaic_str, tile_ct, polynomial
            )
            if result.better_than(prev_best):
                knot_bank[polynomial] = result
    d_time = time() - start_t

    if len(bad_mosaics):
        print(f"Bad Mosaics in {in_file}", flush=True)
    with out_file.open("w") as out:
        lines = [(r.to_str() + "\n") for r in knot_bank.values()]
        out.writelines(lines)
        out.write("END_RESULT")

    print(
        f"Parsed {line_ct:,} from {in_file} in {d_time:.0f}s"
        + f" ({line_ct/d_time:.0f} lines/s)",
        flush=True,
    )
    return list(knot_bank.values()), line_ct


def handle_str(args):
    mosaic_str: str = args.string
    builder = M.parser_types[args.type]
    mosaic = builder(mosaic_str)

    knot = M.traverse_mosaic(mosaic)
    if type(knot) is str:
        print(f"Bad Mosaic: {mosaic_str}")
        return
    knot = make_knot(knot)  # type: ignore
    if not knot or not knot.is_knot():  # type:ignore
        print("Mosaic is not a knot")
        return
        # knot = knot.simplify(exhaustive=True, height=3)
    knot = knot.simplify()  # type: ignore
    knotinfo = str(knot.get_knotinfo())
    polynomial = str(knot.homfly_polynomial())
    print(f"{mosaic_str} || {knotinfo} || {polynomial}")

    img_path = Path(f"output/other_img/{mosaic_str.strip()}.png")
    mvis.gen_png(mosaic, mosaic_str, knotinfo, img_path)


if __name__ == "__main__":
    main()
