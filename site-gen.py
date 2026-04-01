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

from pathlib import Path
from PIL import Image
import mosaic_vis as mvis

# PIL is only imported when actually needed (inside _save_images).
# This keeps the script importable even without Pillow if you only need
# to inspect or extend the generation logic.

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

# list of dicts: {knot_id, values, pil_images}
rows = []


def add_row(knot_id: str, values: list[int | None], images: list[Image.Image | None]):
    """
    Add a row to the table.

    Args:
        knot_id: KnotInfo-style ID, e.g. "3_1"
        values:  List of exactly 6 numbers (one per N-side column, N=1..6).
                 Use None to leave a cell empty.
        images:  List of exactly 6 entries. Each entry is either:
                   - a PIL Image object  -> saved to images/<knot_id>_N<col>.png
                   - None               -> cell has no image
    """
    if len(values) != 6:
        raise ValueError("values must have exactly 6 entries")
    if len(images) != 6:
        raise ValueError("images must have exactly 6 entries")
    rows.append(
        {"knot_id": knot_id, "values": list(values), "pil_images": list(images)}
    )


# ---------------------------------------------------------------------------
# Image saving
# ---------------------------------------------------------------------------


def _save_images(row: dict, images_dir: Path) -> list:
    """
    Save any PIL Image objects in a row to disk.
    Returns a list of 6 relative image paths (or None where no image exists).
    """

    paths = []
    for col_index, img in enumerate(row["pil_images"], start=1):
        if img is None:
            paths.append(None)
        else:
            if not isinstance(img, Image.Image):
                raise TypeError(
                    f"images entries must be PIL Image objects or None; "
                    f"got {type(img)} for knot {row['knot_id']} column {col_index}"
                )
            filename = f"{row['knot_id']}_N{col_index}.png"
            img.save(images_dir / filename)
            # Path stored in the HTML is relative to the HTML file itself
            paths.append(f"images/{filename}")
    return paths


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


def _build_cell(value:int, image_path, col_index: int) -> str:
    """Return a <td> element for a single table cell."""
    if value is None or value == "":
        return "    <td></td>"

    val_str = _escape(str(value))

    if not image_path:
        return f"    <td>{val_str}</td>"

    img_js = _js_escape(image_path)
    val_js = _js_escape(val_str)
    return (
        f"    <td>"
        f'<span class="cell-value" '
        f"onclick=\"showOverlay('{img_js}', '{val_js}', {col_index})\">"
        f"{val_str}</span>"
        f"</td>"
    )


def _build_table_body(saved_paths_per_row: list) -> str:
    """Render all <tr> elements as a single string."""
    table_rows = []
    for row, img_paths in zip(rows, saved_paths_per_row):
        knot_id = row["knot_id"]
        url = f"https://knotinfo.org/diagram_display.php?{knot_id}"
        cells = [
            f"    <td class='knot-id'><a href='{url}' target='_blank'>{_escape(knot_id)}</a></td>"
        ]
        for i, (val, img_path) in enumerate(zip(row["values"], img_paths)):
            cells.append(_build_cell(val, img_path, i + 1))
        table_rows.append("  <tr>\n" + "\n".join(cells) + "\n  </tr>")
    return "\n".join(table_rows)


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------


def generate_html(
    output_path: Path,
    template_path: Path,
):
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

    # Save images and collect their relative paths
    saved_paths_per_row = [_save_images(row, images_dir) for row in rows]

    # Build the table body HTML
    table_body = _build_table_body(saved_paths_per_row)

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

if __name__ == "__main__":
    from PIL import Image, ImageDraw

    def _placeholder(label: str, color: str = "#aaddff") -> Image.Image:
        """Tiny labeled image for demo purposes."""
        img = Image.new("RGB", (200, 200), color)
        draw = ImageDraw.Draw(img)
        draw.text((10, 90), label, fill="#000000")
        return img

   
    add_row(
        "3_1",
        values=[None, None, 4, 5, 5, 6],
        images=[
            None,
            None,
            _placeholder("3_1 N=3"),
            _placeholder("3_1 N=4"),
            _placeholder("3_1 N=5"),
            _placeholder("3_1 N=6"),
        ],
    )

    generate_html(
        output_path=Path("cubic_site/knot_table.html"),
        template_path=Path("site_template.html"),
    )
