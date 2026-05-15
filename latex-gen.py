

from pathlib import Path


def main():
    knotIDs = get_knot_ids()
    print(knotIDs)

    cyl_folder = Path("output/cyl_imgs")
    mobius_folder = Path("output/mobius_imgs")
    for id in knotIDs:
        cyl_img = list(cyl_folder.glob(f"*-K{id}-*"))
        mob_img = list(mobius_folder.glob(f"*-K{id}-*"))
        print(id,":")
        if cyl_img:
            print("- cyl", get_knot_str(cyl_img[0]))
        if mob_img:
            print("- mob", get_knot_str(mob_img[0]))


def get_knot_str(filename: Path):
    return filename.stem.split("-")[-1]

def get_knot_ids():
    knotIDs = []
    for n, ct in enumerate([0, 0, 0, 1, 1, 2, 3, 7, 21]):
        IDs = [f"{n}_{i+1}" for i in range(ct)]
        knotIDs.extend(IDs)
    return knotIDs


if __name__ == "__main__":
    exit(main())