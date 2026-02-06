import argparse
import os
from pathlib import Path
from PIL import Image, ImageDraw
from dataclasses import dataclass
import mosaic_tools as mtool
from sage.all import Link


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--images', help='Print image(s)', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',
                        help='Determine knot type from string')

    args = parser.parse_args()

    mat = mtool.string2matrix(args.string)


class toric_mosaic:
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

    @classmethod
    def string_catalog(cls, mosaic_string, images):
        size = int(len(mosaic_string)**(0.5))
        mosaic = [[10]*(size**2)]  # ASK: why initialize to 10?
        mosaic.append([10]*(size**2))
        satisfied = [[False]*(size ** 2)]*2
        crossing_strands = [
            [[0]*4 for _ in range((size ** 2))] for _ in range(2)]
        # this line is redundant?
        made_connections = [[[] for _ in range((size ** 2))] for _ in range(2)]

        knot = None
        made_connections = [[[] for _ in range(size ** 2)] for _ in range(2)]
        crossing_indices = []
        pd_codes = []
        # Layer 0 "front", 1 holds hidden crossings
        curr_tile = layer = face = 0
        starting_tile = None
        strand_number = 1

        k = num = 0
        for char in mosaic_string.strip():
            num = int(char, base=16)
            mosaic[0][k] = num
            satisfied[0][k] = num == 0
            # Starting tile is set to the first non-zero tile
            if starting_tile == None and num != 0:
                starting_tile = k
            k += 1

        # initializing "rear"
        satisfied[1] = [False]*(size**2)
        mosaic[1] = [0]*(size**2)
        for i in range(size):
            # iterating through columns edges?
            if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1, 4, 5):
                for j in range(size):
                    # ASK: adding 5 to the whole row? Other one adds 6 if it is on top edge?
                    mosaic[1][i*size + j] += 5
            # iterating through top row edge?
            if mosaic[0][i] > 6 or mosaic[0][i] in (3, 4, 6):
                for j in range(size):
                    mosaic[1][(j+1)*size - (i+1)] += 6
        
        # clear some errors
        assert (starting_tile is not None)
        curr_tile = starting_tile
        tile = mosaic[layer][curr_tile]
        face = cls.valid_connections[tile][0][0]
        not_looped = True
        while not_looped:
            for conn in cls.valid_connections[mosaic[layer][curr_tile]]:
                if conn[0] == face:
                    if conn in made_connections[layer][curr_tile]:
                        not_looped = False
                        break
                    made_connections[layer][curr_tile].append(conn)
                    if ((len(made_connections[layer][curr_tile]) == 1) and mosaic[layer][curr_tile] < 7) or (len(made_connections[layer][curr_tile]) == 2):
                        satisfied[layer][curr_tile] = True

                    # Crossing logic
                    if mosaic[layer][curr_tile] > 8:
                        if satisfied[layer][curr_tile]:
                            crossing_indices.append([layer, curr_tile])
                        crossing_strands[layer][curr_tile][face] = strand_number
                        strand_number += 1
                        crossing_strands[layer][curr_tile][(
                            face + 2) % 4] = strand_number
                    else:
                        face = (conn[1] + 2) % 4

                    # Go to next tile
                    if face == 0:  # left
                        if curr_tile % size == 0:
                            layer = (layer + 1) % 2
                            curr_tile = size*((curr_tile//size) + 1) - 1
                        else:
                            curr_tile -= 1
                    elif face == 1:  # down
                        if (curr_tile // size) == size - 1:
                            layer = (layer + 1) % 2
                            curr_tile = size**2 - (curr_tile % size + 1)
                            face = 3
                        else:
                            curr_tile += size
                    elif face == 2:  # right
                        if curr_tile % size == size - 1:
                            layer = (layer + 1) % 2
                            curr_tile = size*(curr_tile // size)
                        else:
                            curr_tile += 1
                    elif face == 3:  # up
                        if curr_tile // size == 0:
                            layer = (layer + 1) % 2
                            curr_tile = size - (curr_tile + 1)
                            face = 1
                        else:
                            curr_tile -= size
                    break
        if all(satisfied[0]):
            if len(crossing_indices) < 3:
                homf = 1
            else:
                for index in crossing_indices:
                    if mosaic[index[0]][index[1]] == 9:
                        if (0, 2) in made_connections[index[0]][index[1]]:
                            pd_codes.append(
                                crossing_strands[index[0]][index[1]])
                        else:
                            # Rotated by 2
                            pd_codes.append(
                                crossing_strands[index[0]][index[1]][2:] + crossing_strands[index[0]][index[1]][:2])
                    else:
                        if (1, 3) in made_connections[index[0]][index[1]]:
                            pd_codes.append(
                                crossing_strands[index[0]][index[1]][1:] + crossing_strands[index[0]][index[1]][:1])
                        else:
                            pd_codes.append(
                                crossing_strands[index[0]][index[1]][3:] + crossing_strands[index[0]][index[1]][:3])
                for l in range(len(pd_codes[-1])):
                    if pd_codes[-1][l] == strand_number:
                        pd_codes[-1][l] = 1
                        break
                knot = Link(pd_codes).remove_loops()
                if images:
                    to_png(mosaic[0], f"images/{mosaic_string.strip()}.png")
                print(knot.pd_code(), knot.homfly_polynomial())

    @classmethod
    def file_catalog(cls, input_path: Path, output_path: Path, images: bool):
        knot_catalog = dict()

        input_file = open(input_path, 'r')
        output_file = open(output_path, 'w')

        test_string = input_file.readline().strip()
        size = int(len(test_string)**(0.5))
        mosaic = [[10]*(size**2)]
        mosaic.append([10]*(size**2))
        satisfied = [[False]*(size ** 2)]*2
        crossing_strands = [
            [[0]*4 for _ in range((size ** 2))] for _ in range(2)]
        made_connections = [[[] for _ in range((size ** 2))] for _ in range(2)]
        crossing_indices = []
        pd_codes = []
        curr_tile = 0
        layer = 0  # 0 "front", 1 holds hidden crossings
        starting_tile = None
        face = 0
        strand_number = 1
        i = 0
        num = 0
        knot_count = 0

        knot = None
        for mosaic_string in input_file:
            made_connections = [[[]
                                 for _ in range(size ** 2)] for _ in range(2)]
            crossing_indices = []
            pd_codes = []
            curr_tile = layer = face = 0
            starting_tile = None
            strand_number = 1

            k = num = 0
            for char in mosaic_string.strip():
                num = int(char, base=16)
                mosaic[0][k] = num
                satisfied[0][k] = num == 0
                if starting_tile == None and num != 0:
                    starting_tile = k
                k += 1

            # initializing "rear"
            satisfied[1] = [False]*(size**2)
            mosaic[1] = [0]*(size**2)
            for i in range(size):
                if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1, 4, 5):
                    for j in range(size):
                        mosaic[1][i*size + j] += 5
                if mosaic[0][i] > 6 or mosaic[0][i] in (3, 4, 6):
                    for j in range(size):
                        mosaic[1][(j+1)*size - (i+1)] += 6

            curr_tile = starting_tile
            face = cls.valid_connections[mosaic[layer][curr_tile]][0][0]
            not_looped = True
            while not_looped:
                for conn in cls.valid_connections[mosaic[layer][curr_tile]]:
                    if conn[0] == face:
                        if conn in made_connections[layer][curr_tile]:
                            not_looped = False
                            break
                        made_connections[layer][curr_tile].append(conn)
                        if ((len(made_connections[layer][curr_tile]) == 1) and mosaic[layer][curr_tile] < 7) or (len(made_connections[layer][curr_tile]) == 2):
                            satisfied[layer][curr_tile] = True

                        # Crossing logic
                        if mosaic[layer][curr_tile] > 8:
                            if satisfied[layer][curr_tile]:
                                crossing_indices.append([layer, curr_tile])
                            crossing_strands[layer][curr_tile][face] = strand_number
                            strand_number += 1
                            crossing_strands[layer][curr_tile][(
                                face + 2) % 4] = strand_number
                        else:
                            face = (conn[1] + 2) % 4

                        # Go to next tile
                        if face == 0:  # left
                            if curr_tile % size == 0:
                                layer = (layer + 1) % 2
                                curr_tile = size*((curr_tile//size) + 1) - 1
                            else:
                                curr_tile -= 1
                        elif face == 1:  # down
                            if (curr_tile // size) == size - 1:
                                layer = (layer + 1) % 2
                                curr_tile = size**2 - (curr_tile % size + 1)
                                face = 3
                            else:
                                curr_tile += size
                        elif face == 2:  # right
                            if curr_tile % size == size - 1:
                                layer = (layer + 1) % 2
                                curr_tile = size*(curr_tile // size)
                            else:
                                curr_tile += 1
                        elif face == 3:  # up
                            if curr_tile // size == 0:
                                layer = (layer + 1) % 2
                                curr_tile = size - (curr_tile + 1)
                                face = 1
                            else:
                                curr_tile -= size
                        break

            if all(satisfied[0]):
                knot_count += 1
                if len(crossing_indices) < 3:
                    homf = 1
                else:
                    for index in crossing_indices:
                        if mosaic[index[0]][index[1]] == 9:
                            if (0, 2) in made_connections[index[0]][index[1]]:
                                pd_codes.append(
                                    crossing_strands[index[0]][index[1]])
                            else:
                                # Rotated by 2
                                pd_codes.append(
                                    crossing_strands[index[0]][index[1]][2:] + crossing_strands[index[0]][index[1]][:2])
                        else:
                            if (1, 3) in made_connections[index[0]][index[1]]:
                                pd_codes.append(
                                    crossing_strands[index[0]][index[1]][1:] + crossing_strands[index[0]][index[1]][:1])
                            else:
                                pd_codes.append(
                                    crossing_strands[index[0]][index[1]][3:] + crossing_strands[index[0]][index[1]][:3])
                    for l in range(len(pd_codes[-1])):
                        if pd_codes[-1][l] == strand_number:
                            pd_codes[-1][l] = 1
                            break
                    homf = Link(pd_codes).homfly_polynomial()
                if not homf in knot_catalog:
                    knot_catalog[homf] = mosaic_string.strip()
                    output_file.write(f"\t{homf}: {knot_catalog[homf]}\n")
                    output_file.flush()
                    if images:
                        img_path = f"images/{output_path.stem}/{mosaic_string.strip()}.png"
                        to_png(mosaic[0], img_path)
        print(knot_count)
        output_file.close()


def to_png(matrix, output_filename):
    img = mtool.to_img(matrix)
    Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_filename)


if __name__ == "__main__":
    main()
