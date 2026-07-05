from itertools import batched
from pathlib import Path
from typing import Iterable
from natsort import natsorted

import mosaic_util as util


def build_line(subfigures: Iterable[str]):
    return (
        "\n".join(
            (
                r"\begin{figure}[h]\centering\captionsetup[subfigure]{labelformat=empty}",
                "\n".join(subfigures),
                r"\end{figure}",
            )
        )
        + "\n"
    )


def build_subfigure(knot_file_name: str, folder: Path):
    final_path = folder / knot_file_name
    knotID = knotID_from_filename(knot_file_name)
    return "".join(
        (
            r"\begin{subfigure}{1.55in}\includegraphics[width=1.4in]{",
            str(final_path),
            r"}\caption{$",
            latex_knotID(knotID),
            r"$}\end{subfigure}",
        )
    )

def latex_knotID(knotID:str):
    pt = knotID.split("_")
    return pt[0]+"_{"+pt[1]+"}"

def knotID_from_filename(filename: str):
    return filename.split("-")[1]


# Not sure if this is needed?
def get_knot_ids():
    knotIDs = []
    for n, ct in enumerate([0, 0, 0, 1, 1, 2, 3, 7, 21]):
        IDs = [f"{n}_{i+1}" for i in range(ct)]
        knotIDs.extend(IDs)
    return knotIDs


def filter_order(max_order):
    """Returns a function that will be true for any file with knot <= `max_order`"""
    return lambda file: util.knot_order_from_id(knotID_from_filename(file)) <= max_order


def filter_good_knotresult(img_name) -> bool:
    id_sect = img_name.split("-")[1]
    # no results that errored
    if "E_SAGE" in id_sect:
        return False
    # no results with unknown ID
    if "," in id_sect:
        return False
    return True


def gen_latex(
    inp_folder: Path, out_file: Path, out_folder: Path, max_order=float("inf")
):
    # get file names
    files = (f.name for f in inp_folder.glob("*.png"))
    # filter out errored results
    files = filter(filter_good_knotresult, files)
    # filter out high-results
    files = filter(filter_order(max_order), files)
    # sort them
    files = natsorted(files, lambda f: knotID_from_filename(f))

    # build subfigs from filenames
    subfigs = (build_subfigure(f, out_folder) for f in files)
    # batch them into rows
    figures = (build_line(row) for row in batched(subfigs, 3))

    # write them to a file
    with out_file.open("w") as f:
        f.writelines(figures)


def main():
    knotIDs = get_knot_ids()

    cyl_folder = Path("output/cyl_imgs")
    cyl_res = Path("output/cyl_census.tex")
    gen_latex(cyl_folder, cyl_res, Path("Images/cyl_census"))
    mobius_folder = Path("output/mobius_imgs")
    mobius_res = Path("output/mobius_census.tex")
    gen_latex(mobius_folder, mobius_res, Path("Images/mobius_census"), max_order=8)


if __name__ == "__main__":
    exit(main())
