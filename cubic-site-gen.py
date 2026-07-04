"""
generate_knot_table.py

Generates a static HTML file displaying a knot mosaic table.

Files produced (all in the same output directory):
  knot_table.html   — the main page
  images/           — PNG files saved from the PIL Images you provide

Usage:
    Call add_row() once per knot, then call generate_html().
    See the __main__ block at the bottom for an example.


THIS SCRIPT WAS PRIMARILY GENERATED WITH CLAUDE AI
Modifications were made by hand to generated code to integrate
it with the rest of the knot-mosaic code.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator


import mosaic_util as util
import mosaic_vis as mvis
import mosaics as M
from polynomial_standardization import HOMFLY, KnotIDDB
import sage_funcs


@dataclass
class CubicResult(util.KnotResult):
    face_ct: int

    @classmethod
    def from_result(cls, res: util.KnotResult, face_ct: int) -> "CubicResult":
        return CubicResult(
            res.size, res.mosaic_str, res.tile_ct, res.polynomial, res.knotID, face_ct
        )


def cubic_better_than(first: CubicResult, second: CubicResult | None) -> bool:
    """Returns true if the first result is preferred over the second"""
    if second is None:
        return True
    # if they have different face count, whichever has fewer faces is better.
    if first.face_ct != second.face_ct:
        return first.face_ct < second.face_ct
    if first.tile_ct != second.tile_ct:
        return first.tile_ct < second.tile_ct
    return int(first.mosaic_str, 16) < int(second.mosaic_str, 16)


@dataclass
class TableEntry:
    knot_id: str
    knot_res: CubicResult
    faces: int
    image_path: Path


def clean_id(knot_id: str):
    """A knot ID cleaned of all lettering, in a #_# form"""
    return knot_id.strip().removeprefix("K").replace("m", "")


@dataclass
class KnotRow:
    knot_id: str
    values: list[TableEntry | None]


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


def _build_cell(value: TableEntry | None, img_path: Path | None, col_index: int) -> str:
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
                img_file = val.image_path.relative_to(imgs_rel_to)
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


class KnotIDTable:
    """Stores the best knot results by Knot ID and size."""

    @classmethod
    def _key_gen(cls, knotID: str, size: int) -> str:
        return f"{knotID}-{size}"

    def get(self, knotID: str, size: int) -> CubicResult | None:
        return self.table.get(self._key_gen(knotID, size))

    def __init__(self, knot_results: Iterable[CubicResult], lut: KnotIDDB):

        self.table: dict[str, CubicResult] = {}
        for res in knot_results:
            # build mosaic
            if res.face_ct == 1:
                mosaic = M.NormMosaic.build_flat(res.mosaic_str)
            else:
                mosaic = M.NormMosaic.build_cubic(res.mosaic_str)
            
            # getting polynomial from mosaic
            pd = M.traverse_mosaic(mosaic, prune_unknots=False)
            assert type(pd) is list
            
            # get knot, polynomial (slow)
            knot = sage_funcs.make_knot(pd)
            poly = HOMFLY.from_knot(knot)
            # possible knot IDs based on polynomial
            knotIDs = lut.lookup(poly)

            # this discards any knots that only
            if knotIDs is None:
                continue
            # a polynomial may have multiple possible knot IDs
            # this saves the best result for each knotID+size
            # TODO: This is incorrect, its assuming the parsed mosaic is ALL the candidate knot IDs
            for id in knotIDs:
                key = self._key_gen(id, res.size)
                if cubic_better_than(res, self.table.get(key)):
                    self.table[key] = res


def zip_and_save(output_file: Path, downloads: Path):
    zip_name = output_file.parent / "cubic_site.zip"
    if zip_name.exists():
        zip_name.unlink()
    zip = shutil.make_archive(zip_name.stem, "zip", "cubic_site")
    shutil.move(zip, zip_name)
    shutil.copy(zip_name, downloads)
    print(f"site saved to {zip_name.absolute()}")


def combine_results_cubic() -> Iterable[CubicResult]:
    """Takes a dir of knot results and combines them, selecting the lowest tile # for each knot"""

    cubics = [
        "2",
        "3_bent",
        "3_line",
        "4_line",
        "4_t",
        "5",
        "6",
    ]

    # Key for categorizing knot results
    # maps polynomial/size to knot result
    @dataclass(frozen=True)
    class ResKey:
        polynomial: str
        size: int

    polynomial_results: dict[ResKey, CubicResult] = {}

    # Build list of folders and sizes
    cubic_res_dirs: list[tuple[Path, int]] = [(util.results_dir("flat"), 1)]
    for c_type in cubics:
        cubic_res_dirs.append((util.results_dir("cubic", c_type), int(c_type[0])))

    # Returns the best result for each polynomial, at each size
    # Best defined as lowest face ct, then lowest tile ct.
    def result_iterator() -> Iterator[CubicResult]:
        """Iterate through all (intermediate, data/cubic_res) cubic result files, for each type of cubic result.
        Yeilds a cubic result for each result item."""
        for res_dir, face_ct in cubic_res_dirs:
            print(f"Parsing {res_dir}...")

            for file in res_dir.glob("*"):
                results, complete = util.load_result_file(file, use_dep=True)
                if not complete:
                    print(f"WARN: {file} is incomplete")
                for res in results:
                    yield CubicResult.from_result(res, face_ct)

    for res in result_iterator():
        res_key = ResKey(res.polynomial, res.size)
        prev_best = polynomial_results.get(res_key)

        # Keep whichever knot result is better
        if cubic_better_than(res, prev_best):
            polynomial_results[res_key] = res
    return polynomial_results.values()


def main():
    # setup destination
    output_file = Path("cubic_site/knot_table.html")
    images_dir = output_file.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    needed_knotIDs = []
    #                       0_       3_ 4_ 5_ 6_ 7_ 8_
    for n, ct in enumerate([1, 0, 0, 1, 1, 2, 3, 7, 21]):
        IDs = [f"{n}_{i + 1}" for i in range(ct)]
        needed_knotIDs.extend(IDs)

    # call out to combine results...
    results = combine_results_cubic()
    # sort results by knotID and size, keep the best result
    print("Building LUT")
    lut = KnotIDDB(max_size=8)
    print("Identifying Knots")
    res_id_table = KnotIDTable(results, lut)

    # Build table of the ones we care about and gen images
    rows = []
    for knot in needed_knotIDs:
        values: list[TableEntry | None] = []
        for col in range(1, 7):
            res = res_id_table.get(knot, col)
            if res is None:
                values.append(None)
                continue

            # build mosaic image
            img_file = images_dir / f"{knot}_N{res.size}.png"
            print(f"generating image: {img_file}")
            if res.face_ct == 1:
                mosaic = M.NormMosaic.build_flat(res.mosaic_str)
            else:
                mosaic = M.NormMosaic.build_cubic(res.mosaic_str, True)
            mvis.gen_png(mosaic, res.mosaic_str, knot, img_file)

            # build table entry
            values.append(TableEntry(knot, res, res.face_ct, img_file))

        rows.append(KnotRow(knot, values))
    # results table is now a list of the best knot result, for every knot at every size (that's been generated)

    generate_html(
        output_path=output_file,
        template_path=Path("site_template.html"),
        data=rows,
    )
    print("Zipping site...")
    downloads = Path("/mnt/c/Users/westn/Downloads/")
    zip_and_save(output_file, downloads)


if __name__ == "__main__":
    exit(main())
