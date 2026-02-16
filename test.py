#!/usr/bin/env python
# shebang will run using whatever python env is activated

import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from random import random
import sys
import threading
from time import sleep
import mosaic_tools as mtool
import matplotlib.pyplot as plt
from multiprocessing import Pool


def show_str(mosaic: str):
    mat = mtool.string2matrix(mosaic)
    img = mtool.to_img(mat)
    plt.imshow(img)
    plt.show()


if __name__ == '__main__':
    show_str('100025512a12aaa5aa7754343')
