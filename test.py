from pathlib import Path
from time import sleep
import mosaic_tools as mtool
import matplotlib.pyplot as plt
from multiprocessing import Pool
from cylindrical import Knot_Result

def show_str(mosaic:str):
    mat = mtool.string2matrix(mosaic)
    img = mtool.to_img(mat)
    plt.imshow(img)
    plt.show()

# show_str('000012127aaa3434')


def f(x: Path):
    print(x)
    sleep(0.1)
    return True

if __name__ == '__main__':
    
    k = Knot_Result("testid", "12345", "12x+3")
    print(k)