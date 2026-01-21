#! /home/westie/miniforge3/envs/sage/bin/python
from PIL import Image, ImageDraw
#from snappy import *
from sage.all import *
import sys, argparse, math, os
import math
from ortools.linear_solver import pywraplp

def main():
    parser = argparse.ArgumentParser(
                        prog='toric.py',
                        description='Classification of toric knot mosaics, and generation of torus toric mosaics using 1-braid algorithm',
                        epilog='https://github.com/margekk/toric-mosaics-2025')

    parser.add_argument('-i', '--images', help='Print image(s)', action='store_true')
    parser.add_argument('-s', '--string', metavar='<mosaic string>',help='Determine knot type from string')
    parser.add_argument('-f', '--file',metavar = ('<input file>','<output file>'),nargs=2,help ='Create knot catalog from file')
    parser.add_argument('-r', '--rapunzel',metavar=('<p>', '<q>'),nargs=2,type=int, help='Perform 1-braid algorithm to generate torus knot (p,q)')

    args = parser.parse_args()

    if args.string is not None:
        toric_mosaic.string_catalog(args.string, args.images)
        return

    if args.file is not None:
        toric_mosaic.file_catalog(args.file[0],args.file[1],args.images)

    if args.rapunzel is not None:
        p = args.rapunzel[0]
        q = args.rapunzel[1]
        if math.gcd(p,q) != 1:
            print("p and q must be relatively prime")
            return
        toric_mosaic.rapunzel_mosaic(p,q)
        return

class toric_mosaic:
    valid_connections = (
        (()),
        ((2,3),(3,2)),
        ((0,3),(3,0)),
        ((0,1),(1,0)),
        ((2,1),(1,2)),
        ((2,0),(0,2)),
        ((1,3),(3,1)),
        ((2,3),(3,2),(1,0),(0,1)),
        ((0,3),(3,0),(2,1),(1,2)),
        ((0,2),(1,3),(2,0),(3,1)),
        ((0,2),(1,3),(2,0),(3,1)),
        ((0,2),(1,3),(2,0),(3,1))
    )
    @classmethod
    # Written by Luc Ta, https://github.com/luc-ta/torus-knot-toric-mosaics
    def get_rapunzel_params(cls, p,q):
        # Create the mip solver with the SCIP backend.
        solver = pywraplp.Solver.CreateSolver("SAT")
        if not solver:
            raise Exception("solver issue")

        infinity = solver.infinity()
        # Make h and v non-negative integer variables
        h = solver.IntVar(0.0, infinity, "h")
        v = solver.IntVar(0.0, infinity, "v")

        # First constraint
        solver.Add(-3 * h - v - p + q + 4 >= 0)

        # Second constraint: r >= -R
        solver.Add(q - 2 * (h + v + p) + 4 >= 0)

        # Third constraint: R >= r
        solver.Add(h + 3 * v <= q - 3 * p + 4)

        # Fourth constraint
        solver.Add(h >= v)

        # Optimize n, the size of the toric mosaic.
        solver.Minimize(q - h - v)

        status = solver.Solve()

        if status == pywraplp.Solver.OPTIMAL:
            return [h.solution_value(),v.solution_value()]
        else:
            raise Exception("No Optimal Parameters Found")


    @classmethod
    def rapunzel_mosaic(cls, p, q):
        mosaic = []
        try:
            rapunzel_params = cls.get_rapunzel_params(p,q)
        except Exception as exp:
            print(f"Error: {exp.args}")
            return
        h = int(rapunzel_params[0])
        v = int(rapunzel_params[1])
        r = (p+v) - h if v != 0 else 2 - h
        n = q - h - v
        print(f"n = {n}\nh = {h}\nv = {v}")
        for i in range(0,p-2):
            mosaic.extend([7]*n)
        for i in range(0,h):
            row = [7]*i + [9]*(p-1)
            row.extend([7]*(n-len(row)))
            mosaic.extend(row)
        if v != 0:
            for i in range(0,(p+v-2)):
                row = [8]*(max(h-i-1,h-v)) + [10]*(min(i + 1,p-1,v,(p+v-2)-i))
                row.extend([8]*(n-len(row)))
                mosaic.extend(row)
        if r < 0:
            for i in range(0,abs(r)):
                mosaic.extend([8]*n)
        if r > 0:
            for i in range(0, abs(r)):
                mosaic.extend([7]*n)
        while len(mosaic) < n**2:
            mosaic.extend([6]*(n))

        for i in range(0, len(mosaic)):
            if i % n == 0:
                print("")
            print(f"{mosaic[i]:x}", end = "")

        to_png(mosaic, f"images/{p},{q}:{n}n,{h}h,{v}v.png")


    @classmethod
    def string_catalog(cls, mosaic_string, images):
        size = int(len(mosaic_string)**(0.5))
        mosaic = [[10]*(size**2)] # ASK: why initialize to 10?
        mosaic.append([10]*(size**2))
        satisfied = [[False]*(size ** 2)]*2
        crossing_strands = [[[0]*4 for _ in range((size ** 2))] for _ in range(2)]
        made_connections = [[[] for _ in range((size ** 2))] for _ in range(2)] #this line is redundant?
        crossing_indices = []
        pd_codes = []
        curr_tile = 0
        layer = 0 #0 "front", 1 holds hidden crossings
        starting_tile = None
        face = 0
        strand_number = 1
        i = 0
        num = 0

        knot = None
        made_connections = [[[] for _ in range(size ** 2)] for _ in range(2)]
        crossing_indices = []
        pd_codes = []
        curr_tile = layer = face = 0
        starting_tile = None
        strand_number = 1

        k = num = 0
        for char in mosaic_string.strip():
            num = int(char, base = 16)
            mosaic[0][k] = num
            satisfied[0][k] = num == 0
            # Starting tile is set to the first non-zero tile
            if starting_tile == None and num != 0:
                starting_tile = k
            k += 1

        #initializing "rear"
        satisfied[1] = [False]*(size**2)
        mosaic[1] = [0]*(size**2)
        for i in range(size):
            # iterating through columns edges?
            if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1,4,5):
                for j in range(size):
                    mosaic[1][i*size + j] += 5 # ASK: adding 5 to the whole row? Other one adds 6 if it is on top edge?
            # iterating through top row edge?
            if mosaic[0][i] > 6 or mosaic[0][i] in (3,4,6):
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

                    #Crossing logic
                    if mosaic[layer][curr_tile] > 8:
                        if satisfied[layer][curr_tile]:
                            crossing_indices.append([layer,curr_tile])
                        crossing_strands[layer][curr_tile][face] = strand_number
                        strand_number += 1
                        crossing_strands[layer][curr_tile][(face + 2) % 4] = strand_number
                    else:
                        face = (conn[1] + 2) % 4

                    #Go to next tile
                    if face == 0: #left
                        if curr_tile%size == 0:
                            layer = (layer + 1)%2
                            curr_tile = size*((curr_tile//size) + 1) - 1
                        else:
                            curr_tile -= 1
                    elif face == 1: #down
                        if (curr_tile // size) == size - 1:
                            layer = (layer + 1)%2
                            curr_tile = size**2 - (curr_tile % size + 1)
                            face = 3
                        else:
                            curr_tile += size
                    elif face == 2: #right
                        if curr_tile % size == size - 1:
                            layer = (layer + 1)%2
                            curr_tile = size*(curr_tile // size)
                        else:
                            curr_tile += 1
                    elif face == 3: #up
                        if curr_tile // size == 0:
                            layer = (layer + 1)%2
                            curr_tile = size - (curr_tile + 1)
                            face = 1
                        else:
                            curr_tile -= size
                    break
        if all(satisfied[0]):
            if len(crossing_indices) < 3 :
                homf = 1
            else:
                for index in crossing_indices:
                    if mosaic[index[0]][index[1]] == 9:
                        if (0,2) in made_connections[index[0]][index[1]]:
                            pd_codes.append(crossing_strands[index[0]][index[1]])
                        else:
                            pd_codes.append(crossing_strands[index[0]][index[1]][2:] + crossing_strands[index[0]][index[1]][:2]) #Rotated by 2
                    else:
                        if (1,3) in made_connections[index[0]][index[1]]:
                            pd_codes.append(crossing_strands[index[0]][index[1]][1:] + crossing_strands[index[0]][index[1]][:1])
                        else:
                            pd_codes.append(crossing_strands[index[0]][index[1]][3:] + crossing_strands[index[0]][index[1]][:3])
                for l in range(len(pd_codes[-1])):
                    if pd_codes[-1][l] == strand_number:
                        pd_codes[-1][l] = 1
                        break
                knot = Link(pd_codes).remove_loops()
                if images:
                        to_png(mosaic[0],f"images/{mosaic_string.strip()}.png")
                print(knot.pd_code(), knot.homfly_polynomial())


    @classmethod
    def file_catalog(cls, input_name, output_name, images):
        knot_catalog = dict()

        input_file = open(input_name, 'r')
        output_file = open(output_name, 'w')

        test_string = input_file.readline().strip()
        size = int(len(test_string)**(0.5))
        mosaic = [[10]*(size**2)]
        mosaic.append([10]*(size**2))
        satisfied = [[False]*(size ** 2)]*2
        crossing_strands = [[[0]*4 for _ in range((size ** 2))] for _ in range(2)]
        made_connections = [[[] for _ in range((size ** 2))] for _ in range(2)]
        crossing_indices = []
        pd_codes = []
        curr_tile = 0
        layer = 0 #0 "front", 1 holds hidden crossings
        starting_tile = None
        face = 0
        strand_number = 1
        i = 0
        num = 0
        knot_count = 0

        knot = None
        for mosaic_string in input_file:
            made_connections = [[[] for _ in range(size ** 2)] for _ in range(2)]
            crossing_indices = []
            pd_codes = []
            curr_tile = layer = face = 0
            starting_tile = None
            strand_number = 1

            k = num = 0
            for char in mosaic_string.strip():
                num = int(char, base = 16)
                mosaic[0][k] = num
                satisfied[0][k] = num == 0
                if starting_tile == None and num != 0:
                    starting_tile = k
                k += 1

            #initializing "rear"
            satisfied[1] = [False]*(size**2)
            mosaic[1] = [0]*(size**2)
            for i in range(size):
                if mosaic[0][i*size] > 6 or mosaic[0][i*size] in (1,4,5):
                    for j in range(size):
                        mosaic[1][i*size + j] += 5
                if mosaic[0][i] > 6 or mosaic[0][i] in (3,4,6):
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

                        #Crossing logic
                        if mosaic[layer][curr_tile] > 8:
                            if satisfied[layer][curr_tile]:
                                crossing_indices.append([layer,curr_tile])
                            crossing_strands[layer][curr_tile][face] = strand_number
                            strand_number += 1
                            crossing_strands[layer][curr_tile][(face + 2) % 4] = strand_number
                        else:
                            face = (conn[1] + 2) % 4

                        #Go to next tile
                        if face == 0: #left
                            if curr_tile%size == 0:
                                layer = (layer + 1)%2
                                curr_tile = size*((curr_tile//size) + 1) - 1
                            else:
                                curr_tile -= 1
                        elif face == 1: #down
                            if (curr_tile // size) == size - 1:
                                layer = (layer + 1)%2
                                curr_tile = size**2 - (curr_tile % size + 1)
                                face = 3
                            else:
                                curr_tile += size
                        elif face == 2: #right
                            if curr_tile % size == size - 1:
                                layer = (layer + 1)%2
                                curr_tile = size*(curr_tile // size)
                            else:
                                curr_tile += 1
                        elif face == 3: #up
                            if curr_tile // size == 0:
                                layer = (layer + 1)%2
                                curr_tile = size - (curr_tile + 1)
                                face = 1
                            else:
                                curr_tile -= size
                        break

            if all(satisfied[0]):
                knot_count += 1
                if len(crossing_indices) < 3 :
                    homf = 1
                else:
                    for index in crossing_indices:
                        if mosaic[index[0]][index[1]] == 9:
                            if (0,2) in made_connections[index[0]][index[1]]:
                                pd_codes.append(crossing_strands[index[0]][index[1]])
                            else:
                                pd_codes.append(crossing_strands[index[0]][index[1]][2:] + crossing_strands[index[0]][index[1]][:2]) #Rotated by 2
                        else:
                            if (1,3) in made_connections[index[0]][index[1]]:
                                pd_codes.append(crossing_strands[index[0]][index[1]][1:] + crossing_strands[index[0]][index[1]][:1])
                            else:
                                pd_codes.append(crossing_strands[index[0]][index[1]][3:] + crossing_strands[index[0]][index[1]][:3])
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
                        to_png(mosaic[0],f"images/{output_name}/{mosaic_string.strip()}.png")
        print(knot_count)
        output_file.close()

def to_png(matrix,output_filename):
    tile_size = 64
    border_size = 4
    border_color = (196, 196, 196, 255)
    size = int(len(matrix)**0.5)

    tile_images = {}
    for num in range(11):
        file_name = f"tiles/{num}.png"
        try:
            tile_images[num] = Image.open(file_name).convert("RGBA")
        except FileNotFoundError:
            print(f"Failed to load image {file_name}")

    mosaic_width = size * tile_size + 2 * border_size
    mosaic = Image.new("RGBA", (mosaic_width, mosaic_width), border_color)
    draw = ImageDraw.Draw(mosaic)

    for i, tile in enumerate(matrix):
            if tile in tile_images:
                img_tile = tile_images[tile]
                for y in range(tile_size):
                    for x in range(tile_size):
                        pixel = img_tile.getpixel((x, y))
                        mosaic.putpixel(( (i % size) * tile_size + x + border_size, (i // size) * tile_size + y + border_size), pixel)

    mosaic.save(output_filename)


main()
