#!/usr/bin/env python
# shebang will run using whatever python env is activated

from pathlib import Path
import time

import mosaic_vis as mvis
import matplotlib.pyplot as plt
import mosaics as mos


def show_str(mosaic: str):
    mat = mvis.string2matrix(mosaic)
    img = mvis.build_img(mat)
    plt.ion()
    plt.imshow(img)


def plot_block():
    plt.ioff()
    plt.show()


def iter_folder_lines(folder: Path):
    length = len(list(folder.glob("*.txt")))
    for ind in range(length):
        file = folder / f"pt{ind}.txt"
        print(f"Opening {file}")
        for line in file.open():
            yield line.strip()


def classify_mosaics(folder):

    resCount: dict[mos.NotAKnot, int] = {}
    for type in mos.NotAKnot:
        resCount[type] = 0

    for line in iter_folder_lines(folder):
        mosaic = mos.NormMosaic.build_cylindrical(line)
        result = mos.traverse_mosaic(mosaic, classify_only=True)
        resCount[result] += 1
    for id, ct in resCount.items():
        print(f"{id}: {ct:,}")


if __name__ == "__main__":
    str = "0000102171664343"
    show_str(str)
    mosaic = mos.NormMosaic.build_cylindrical(str)
    print(mos.traverse_mosaic(mosaic))
    plot_block()
    # folder = Path("./data/4_cyl_testV2/")
    # classify_mosaics(folder)
    test_strs = ["0000102171664343", "0000102175463554", "0000102175463554"]
