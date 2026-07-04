#! /usr/bin/env python
from concurrent.futures import Future, ProcessPoolExecutor
from multiprocessing import current_process
from pathlib import Path
import threading
from time import sleep, time
from typing import Callable

import mosaics as M
import mosaic_vis as mvis
import mosaic_util as util
import polynomial_standardization as poly
import arg_parsing


def main():
    parser = arg_parsing.knot_argparser()
    args = parser.parse_args()
    args.func(args)


def handle_file(args):
    # raise NotImplementedError("Implement for multi-type input")
    catalog_files([args.input_file], args.output_file, M.parser_types[args.type],skip_sage=args.no_sage)


def run_catalog(args):
    """Uses multiple processes to parse through a directory of mosaic files"""
    [type, size, keep_existing_results] = [args.type, args.size, args.keep_existing]
    builder: Callable[[str], M.NormMosaic] = M.parser_types[type]

    inp_dir = util.mosaic_dir(type, size, args.cubic_version)
    out_dir = util.results_dir_knotID(type, args.cubic_version)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not inp_dir.is_dir() or len(list(inp_dir.iterdir())) == 0:
        print(f"ERR: no mosaics to process for {inp_dir}")
        return
    if (not (inp_dir / "COMPLETED").is_file()) and (not args.ignore_incomplete):
        print("STOPPING: Mosaic list is not complete")
        print("run with --ignore-incomplete to proceed anyway")
        return

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

    print(f"Parsing from {inp_dir}", flush=True)
    inp_index = 0
    out_index = 0
    exit_flag = False
    max_queue = 8
    futures: dict[Future, int] = {}
    # spawning workers to parse files
    with ProcessPoolExecutor(
        max_workers=args.workers, max_tasks_per_child=3
    ) as executor:
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
                elif args.verbose:
                    print(f"Result {ind} done", flush=True)

            # Queueing new files
            if len(futures) < max_queue:
                in_paths: list[Path] = []
                # taking 3 files as input for each
                for _ in range(3):
                    if (f := inp_dir / f"pt{inp_index:04}.txt").is_file():
                        in_paths.append(f)
                        inp_index += 1
                    else:
                        exit_flag = True

                out_path = out_dir / f"{size}_pt{out_index:04}.txt"
                out_index += 1
                # if output is already generated:
                if out_path.is_file() and keep_existing_results:
                    continue
                # if we're done all the files in the folder, exit
                if args.verbose:
                    print(f"Queued {",".join(f.stem for f in in_paths)}", flush=True)
                fut = executor.submit(
                    catalog_files, in_paths, out_path, builder, args.no_sage
                )
                futures[fut] = out_index - 1

                # stops loop when out of inputs
                if exit_flag:
                    break
            else:
                sleep(1)

        print("waiting for current workers to finish...", flush=True)
        [
            print(f"Working on: {i}, running={fut.running()}")
            for fut, i in futures.items()
        ]
        executor.shutdown(wait=True, cancel_futures=False)
        print("fully shutdown now")


def catalog_files(
    in_files: list[Path], out_file: Path, builder: Callable, skip_sage: bool = False
):
    """Finds all unique knots in a set of files"""

    from sage_funcs import make_knot

    # maps knotID to a result object
    knot_res_byID: dict[str, util.KnotResult] = {}

    # maps polynomials to their knotID(s)
    # Contains all prime knots thru size 13, we don't care about above that
    knotID_DB = poly.KnotIDDB.load_from_file(Path("data/knotIDDB.pkl"))

    # dict Cache mapping all seen PD codes to their knotID.
    # All knots with the same PD codes are the same knot.
    pd_code_cache: dict[str, str] = {}
    # list of mosaics with bad connections
    bad_mosaics: list[str] = []

    # iterating over each line in each file in the dir
    in_files_str = ", ".join(f.stem for f in in_files)
    print(
        f"Starting {in_files_str} on {current_process().name}",
        flush=True,
    )

    # Define an flattened iterator over mosaic strings
    def iter_lines():
        for f_name in in_files:
            with f_name.open("r") as f:
                for mosaic_str in f:
                    yield mosaic_str

    # keep track of how many we've parsed
    line_ct = 0
    start_t = time()
    for mosaic_str in iter_lines():
        line_ct += 1

        # Build mosaic from string
        mosaic_str = mosaic_str.strip()
        mosaic: M.NormMosaic = builder(mosaic_str)
        pd_codes = M.traverse_mosaic(mosaic, prune_unknots=False)
        pd_codes_str = str(pd_codes)

        # discard non-knot mosaics
        if type(pd_codes) is M.NotAKnot:
            match pd_codes:
                case M.NotAKnot.BAD_CONNECTIONS:
                    bad_mosaics.append(f"{pd_codes_str}, {mosaic_str}\n")
            continue

        # If this PD code has been seen before, we already know the polynomial
        knotID = pd_code_cache.get(pd_codes_str)
        if knotID is None:
            # If there's no cached polynomial, calculate it
            knot = make_knot(pd_codes)  # type: ignore
            polynomial = poly.HOMFLY.from_knot(knot)
            knotIDs = knotID_DB.lookup(polynomial)

            if knotIDs is None:
                # No entries in DB, so it's composite or >13 crossings
                continue
            elif len(knotIDs) == 1:
                # This polynomial can only be one knot
                # TODO: Technically it could be a >13 crossing knot that collides
                # with a low-crossing knot. No great way to filter for this
                knotID = knotIDs[0]
            else:
                knotID = disambiguate_knot(knotIDs, knot,skip_sage=skip_sage)
            # cache this pd->knotID relation
            pd_code_cache[pd_codes_str] = knotID

        # Build the new knot result
        tile_ct = util.count_tiles(mosaic_str)
        new_res = util.KnotResult(
            mosaic.nominal_size, mosaic_str, tile_ct, str(polynomial), knotID
        )
        # replace the result for this knot if the new one is better
        prev_best_res = knot_res_byID.get(knotID)
        if new_res.better_than(prev_best_res):
            knot_res_byID[knotID] = new_res
    d_time = time() - start_t

    # Warn about bad mosaics
    if len(bad_mosaics):
        print(f"WARN: Bad Mosaics in {in_files_str}", flush=True)
        [print(mos) for mos in bad_mosaics]

    # write results to file
    with out_file.open("w") as out:
        lines = [(r.to_str() + "\n") for r in knot_res_byID.values()]
        out.writelines(lines)
        out.write("END_RESULT")  # confirms that result was not interrupted

    # print result to console
    print(
        f"Parsed {line_ct:,} from {in_files_str} in {d_time:.0f}s"
        + f" ({line_ct/d_time:.0f} lines/s)",
        flush=True,
    )


def disambiguate_knot(knotIDs: tuple[str, ...], knot, skip_sage: bool = False) -> str:
    # number of crossings of the simplified knot
    # may still be > the minimum-crossing-number
    max_crossings = len(knot.pd_code())
    valid = [id for id in knotIDs if util.knot_size_from_id(id) <= max_crossings]
    if len(valid) == 1:
        return valid[0]

    if skip_sage:
        return ",".join(valid)

    print(f"Using sage to disambiguate: {",".join(valid)}", flush=True)
    # this can be *VERY* slow for some knots. Times out after 60 seconds
    from sage_funcs import get_knotinfo_with_timeout

    knot_info = get_knotinfo_with_timeout(knot, 30)
    if knot_info is None:
        print(f"DISAMBIGUATION_FAILED, Timeout-{",".join(valid)}", flush=True)
        return f"E_SAGE{",".join(valid)}"

    def clean_knot(inp: str) -> str:
        for s in ["KnotInfo", "[", "]", "'", "K", "m"]:
            inp = inp.replace(s, "")
        return inp

    knot_info = [clean_knot(str(knot)) for knot in knot_info]
    if len(knot_info) > 1:
        print(
            f"ERR - Sage failed to disambiguate knots - found {', '.join(knot_info)}",
            flush=True,
        )

    print("--SAGE SUCCESS--", flush=True)
    # cleaning up the KnotInfo output
    return ",".join(knot_info)


def combine_results(args):
    """Takes a dir of knot results and combines them, selecting the lowest tile # for each knot"""
    from natsort import natsorted

    mosaic_type = args.type
    builder = M.parser_types[args.type]
    # check that there are results to merge
    results_folder = util.results_dir_knotID(mosaic_type, args.cubic_version)
    if not results_folder.is_dir() or len(list(results_folder.iterdir())) == 0:
        print(f"ERR: no results to merge for {results_folder}")
        return

    # initialize output folders
    imgs_dir = util.img_dir(mosaic_type, args.cubic_version)
    out_file = util.output_path(mosaic_type, args.cubic_version)
    # mapping from mosaic to knotID
    if imgs_dir.exists():
        [f.unlink() for f in imgs_dir.iterdir()]
    else:
        imgs_dir.mkdir(parents=True)

    # maps knotID to knot result
    all_results: dict[str, util.KnotResult] = {}

    # merge results, keeping lowest tile number
    print("Merging results...")
    for file in results_folder.iterdir():
        results_list, complete = util.load_result_file(file)
        if not complete:
            print(f"{file} is incomplete")
        for res in results_list:
            # Only keep the better knot result
            prev_best = all_results.get(res.knotID)
            if res.better_than(prev_best):
                all_results[res.knotID] = res

    # generate output file
    print("Saving resuts file...")
    results_sorted = natsorted(all_results.values(), key=lambda res: res.knotID)
    with out_file.open("w") as out:
        text = "\n".join(res.to_str() for res in results_sorted)
        out.write(text)

    print("Saving images...")
    count = len(all_results.values())

    for progress, res in enumerate(results_sorted):
        if progress % int(count / 20) == 0:
            print(f"  {progress/count:.0%} - {progress}/{count}")
        mosaic = builder(res.mosaic_str)
        # generating and saving image
        img_path = util.img_filepath(imgs_dir, res)
        if args.publish:
            img = mvis.build_img(mosaic.get_publish_mosaic())
            img.save(img_path)
        else:
            mvis.gen_png(mosaic, res.mosaic_str, res.knotID, img_path)

    print("Done merging")


def handle_str(args):
    mosaic_str: str = args.string
    builder = M.parser_types[args.type]
    mosaic = builder(mosaic_str)

    knot = M.traverse_mosaic(mosaic)
    if type(knot) is str:
        print(f"Bad Mosaic: {mosaic_str}")
        return
    knot = make_knot(knot)  # type: ignore
    if not knot or not knot.is_knot():  # type: ignore
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
