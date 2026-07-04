import argparse
from pathlib import Path
import main
import mosaics as M


def knot_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(help="mode to run in", required=True)
    parser.add_argument(
        "-v", "--verbose", help="enable additional output", action="store_true"
    )

    string = subs.add_parser("string", help="Parse a single string")
    string.add_argument("string", help="Determine knot type from string")
    string.add_argument("type", choices=M.parser_types.keys(), help="type of mosaic")
    string.set_defaults(func=main.handle_str)

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
    parse.add_argument(
        "-w",
        "--workers",
        help="Number of parallel worker-processes to spawn",
        type=int,
        default=6,
    )
    parse.add_argument(
        "-i",
        "--ignore-incomplete",
        help="Allow parsing of incomplete result folders",
        action="store_true",
    )
    parse.add_argument(
        "--no-sage",
        help="skip using sage to disambiguate knots",
        action="store_true",
    )
    parse.set_defaults(func=main.run_catalog)

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
    merge.add_argument(
        "-p",
        "--publish",
        help="generate images in 'published' form - without frame, mobius/toric w/out added crossings, cubic as lower-case t",
        action="store_true",
    )
    merge.set_defaults(func=main.combine_results)

    file = subs.add_parser("file", help="parse single file")
    file.add_argument("input_file", help="path of file to parse", type=Path)
    file.add_argument("output_file", help="path to ouput results to", type=Path)
    file.add_argument("type", help="type of mosaic", type=str)
    file.add_argument(
        "--no-sage",
        help="skip using sage to disambiguate knots",
        action="store_true",
    )
    file.set_defaults(func=main.handle_file)

    return parser
