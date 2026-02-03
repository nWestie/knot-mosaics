import argparse
import os
from PIL import Image, ImageDraw
from dataclasses import dataclass
import mosaic_tools as mtool

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--images', help='Print image(s)', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',
                        help='Determine knot type from string')

    args = parser.parse_args()

    mat = mtool.string2matrix(args.string)


if __name__ == "__main__":
    main()
