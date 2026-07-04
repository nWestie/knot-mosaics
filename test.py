#!/usr/bin/env python
# shebang will run using whatever python env is activated

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Pool
from pathlib import Path
import time

import mosaic_vis as mvis
import matplotlib.pyplot as plt
import mosaics as mos
from polynomial_standardization import KnotIDDB

# def show_str(mosaic: str):
#     mat = mvis.string2tiles(mosaic)
#     img = mvis.build_img(mat)
#     plt.ion()
#     plt.imshow(img)


# def plot_block():
#     plt.ioff()
#     plt.show()


if __name__ == "__main__":
    # pkl_file = Path("data/knotIDDB.pkl")
    # knotDB = KnotIDDB.load_from_file(pkl_file)
    # knotDB.dump_to_file(pkl_file)
    mosaic = mos.NormMosaic.build_cubic("ccc066cccccc066cccccc284ccc3912943912943a12943a12943a1")
    img = mvis.build_img(mosaic.get_publish_mosaic())
    img.save("testimg.png")
    img = mvis.build_img(mosaic)
    img.save("testimg2.png")