"""
generate_knot_table.py

Generates a static HTML file displaying a knot mosaic table.
PIL (Pillow) is required only if you pass Image objects to add_row().

Files produced (all in the same output directory):
  knot_table.html   — the main page
  images/           — PNG files saved from the PIL Images you provide

Usage:
    Call add_row() once per knot, then call generate_html().
    See the __main__ block at the bottom for an example.


THIS SCRIPT GENERATED WITH CLAUDE AI
"""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from PIL import Image
import mosaic_vis as mvis
import mosaic_util as util
import mosaics as M
import main as main_parser

# PIL is only imported when actually needed (inside _save_images).
# This keeps the script importable even without Pillow if you only need
# to inspect or extend the generation logic.

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Result:
    knot_id: str
    knot_res: util.KnotResult
    faces: int
    image_path: Path


def clean_id(knot_id: str):
    return knot_id.strip().removeprefix("K").replace("m", "")


@dataclass
class KnotRow:
    knot_id: str
    values: list[Result | None]


# ---------------------------------------------------------------------------
# HTML helpers
# ---------------------------------------------------------------------------


def _escape(s: str) -> str:
    """Escape special characters for safe HTML insertion."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _js_escape(s: str) -> str:
    """Escape a string for safe use inside a JS single-quoted literal."""
    return s.replace("\\", "\\\\").replace("'", "\\'")


def _build_cell(value: Result | None, img_path: Path | None, col_index: int) -> str:
    """Return a <td> element for a single table cell."""
    if value is None or value == "":
        return "    <td></td>"

    faces_str = _escape(str(value.faces))

    if not img_path:
        return f"    <td>{faces_str}</td>"

    img_js = _js_escape(str(img_path))
    faces_js = _js_escape(faces_str)
    return (
        f"    <td>"
        f'<span class="cell-value" '
        f"onclick=\"showOverlay('{img_js}', '{faces_js}', {col_index})\">"
        f"{faces_str}</span>"
        f"</td>"
    )


def _build_table_body(rows: list[KnotRow], images_dir: Path, imgs_rel_to: Path) -> str:
    """Render all <tr> elements as a single string."""
    table_rows = []
    for row in rows:
        knot_id = row.knot_id
        url = f"https://knotinfo.org/diagram_display.php?{knot_id}"
        cells = [
            f"    <td class='knot-id'><a href='{url}' target='_blank'>{_escape(clean_id(knot_id))}</a></td>"
        ]
        for i, val in enumerate(row.values):
            if val:
                img_file = images_dir / f"{knot_id}_N{i+1}.png"
                shutil.copyfile(val.image_path, img_file)
                img_file = img_file.relative_to(imgs_rel_to)
            else:
                img_file = None
            cells.append(_build_cell(val, img_file, i + 1))
        table_rows.append("  <tr>\n" + "\n".join(cells) + "\n  </tr>")
    return "\n".join(table_rows)


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------


def generate_html(output_path: Path, template_path: Path, data: list[KnotRow]):
    """
    Save all PIL images to an images/ folder next to output_path,
    then render the HTML table by filling in the template.

    Args:
        output_path:   Path for the generated HTML file.
        template_path: Path to the HTML template. Must contain exactly one
                       occurrence of {{TABLE_BODY}} as the insertion point.
    """
    images_dir = output_path.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # Build the table body HTML
    table_body = _build_table_body(data, images_dir, output_path.parent)

    # Load template
    template_file = Path(template_path)
    if not template_file.exists():
        raise FileNotFoundError(f"Template not found: {template_file.resolve()}")
    template = template_file.read_text(encoding="utf-8")

    if "{{TABLE_BODY}}" not in template:
        raise ValueError("Template must contain the placeholder {{TABLE_BODY}}")

    # Inject generated rows and write output
    html = template.replace("{{TABLE_BODY}}", table_body)
    output_path.write_text(html, encoding="utf-8")

    print(f"Generated : {output_path.resolve()}")
    print(f"Images in : {images_dir.resolve()}")


# ---------------------------------------------------------------------------
# Sample usage — replace with your real data
# ---------------------------------------------------------------------------
def _placeholder(label: str, color: str = "#aaddff") -> Image.Image:
    from PIL import Image, ImageDraw

    """Tiny labeled image for demo purposes."""
    img = Image.new("RGB", (200, 200), color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 90), label, fill="#000000")
    return img


def main():
    knotIDs = []
    #                       0_       3_ 4_ 5_ 6_ 7_ 8_
    for n, ct in enumerate([1, 0, 0, 1, 1, 2, 3, 7, 21]):
        IDs = [f"{n}_{i+1}" for i in range(ct)]
        knotIDs.extend(IDs)

    cubics = [
        "2",
        "3_bent",
        "3_line",
        "4_line",
        "4_t",
        "5",
        "6",
    ]
    cubic_types = [(util.img_dir("flat"), util.output_path("flat"), 1)]
    for c_type in cubics:
        img_dir = util.img_dir("cubic", c_type)
        res_file = util.output_path("cubic", c_type)
        if not res_file.is_file():
            continue
        cubic_types.append((img_dir, res_file, int(c_type[0])))

    # dict from knotID and size to lowest face-number result
    # accessed as knot_index[<knotID>_<N>]
    knot_index: dict[str, Result] = {}

    def to_key(k_id, nominal_size) -> str:
        return f"{clean_id(k_id)}_{nominal_size}"

    for img_dir, res_file, faces in cubic_types:
        for line in res_file.open("r"):
            [knot_id, _, res_str] = line.partition("|")
            knot_id = knot_id.strip()
            if clean_id(knot_id) not in knotIDs:
                continue

            res = util.KnotResult.from_str(res_str)
            img = util.img_filepath(img_dir, res, knot_id)

            res = Result(knot_id, res, faces, img)

            key = to_key(knot_id, res.knot_res.size)
            prev_res = knot_index.get(key)
            if not prev_res or res.faces < prev_res.faces:
                knot_index[key] = res
            elif res.knot_res.better_than(prev_res.knot_res):
                knot_index[key] = res

    rows = []
    for id in knotIDs:
        values = [knot_index.get(to_key(id, n)) for n in range(1, 7)]
        rows.append(KnotRow(id, values))

    output_file = Path("cubic_site/knot_table.html")
    generate_html(
        output_path=output_file,
        template_path=Path("site_template.html"),
        data=rows,
    )
    print("Zipping site...")
    downloads = Path("/mnt/c/Users/westn/Downloads/")
    zip_name = output_file.parent / "cubic_site.zip"
    if zip_name.exists():
        zip_name.unlink()
    zip = shutil.make_archive(zip_name.stem, "zip", "cubic_site")
    shutil.move(zip, zip_name)
    shutil.copy(zip_name, downloads)
    print(f"site saved to {zip_name.absolute()}")


def combine_results_cubic(args):
    """Takes a dir of knot results and combines them, selecting the lowest tile # for each knot"""

    from sage_funcs import make_knot

    mosaic_type = args.type
    builder = M.parser_types[args.type]

    results_folder = util.results_dir(mosaic_type, args.cubic_version)
    if not results_folder.is_dir() or len(list(results_folder.iterdir())) == 0:
        print(f"ERR: no results to merge for {results_folder}")
        return

    imgs = util.img_dir(mosaic_type, args.cubic_version)
    if imgs.exists():
        [f.unlink() for f in imgs.iterdir()]
    else:
        imgs.mkdir(parents=True)

    out_file = util.output_path(mosaic_type, args.cubic_version)

    # maps polynomial to knot result
    all_results: dict[str, util.KnotResult] = {}

    # merge results, keeping lowest tile number

    for file in results_folder.iterdir():
        results, complete = main_parser.load_result_file(file)
        if not complete:
            print(f"{file} is incomplete")
        for res in results:
            prev_best = all_results.get(res.polynomial)
            # Only keep the better knot result
            if res.better_than(prev_best):
                all_results[res.polynomial] = res

    # generate images
    print("writing file and images...")
    # tuples of (knotID, polynomial)
    knot_ids: list[tuple[str, util.KnotResult]] = []
    for polynomial, res in all_results.items():
        # yes, I'm re-running the ID/simplify steps.
        # But the alternative is to run knotID on all the result files...
        mosaic = builder(res.mosaic_str)
        knot = M.traverse_mosaic(mosaic, prune_unknots=False)
        if type(knot) is M.NotAKnot:
            print(f"ERR: Not a Knot({type(knot)}): {res.mosaic_str}")
            break
        knot = make_knot(knot)  # type:ignore
        new_knot = knot.simplify()
        if new_knot is not None:
            knot = new_knot
        # this can be quite slow for some knots
        knotid = str(knot.get_knotinfo(unique=False))  # type: ignore
        # cleaning up the KnotInfo output
        for s in ["KnotInfo", "[", "]", "'"]:
            knotid = knotid.replace(s, "")
        img_path = util.img_filepath(imgs, res, knotid)
        mvis.gen_png(mosaic, res.mosaic_str, knotid, img_path)
        print(f"saved: {img_path}")

        knot_ids.append((knotid, res))

    # generate output file
    knot_ids.sort(key=lambda k: k[0])
    padding = max(len(k) for k, _ in knot_ids) + 1
    with out_file.open("w") as out:
        for id, res in knot_ids:
            out.write(f"{id.ljust(padding)}|{res.to_str()}\n")


if __name__ == "__main__":
    exit(main())
