"""
Shared utilities for VCE Music worksheet generators.
Handles ABC notation rendering and ReportLab PDF assembly helpers.
"""

import os
import subprocess
import tempfile

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4


# ---------------------------------------------------------------------------
# ABC → PNG rendering
# ---------------------------------------------------------------------------

# abcm2ps page settings used for each rendered snippet.
# Music always lands on page 2 (page 1 is always blank in abcm2ps output).
_ABC_PAGE_HEADER = """\
%%writefields T 0
%%topmargin 0.3cm
%%botmargin 0.3cm
%%leftmargin 0.5cm
%%rightmargin 0.5cm
"""

def render_abc_to_png(abc_body, output_png, page_w_cm=10, page_h_cm=4,
                      staff_w_cm=None, scale=1.2, resolution=180):
    """
    Render an ABC music snippet to a PNG image.

    abcm2ps always emits a blank page 1 then the music on page 2,
    so we tell Ghostscript to only rasterise page 2.

    abc_body should be a complete ABC tune (X:, M:, L:, K:, notes).
    """
    if staff_w_cm is None:
        staff_w_cm = page_w_cm - 1.0

    header = (
        f"%%pagewidth {page_w_cm}cm\n"
        f"%%pageheight {page_h_cm}cm\n"
        f"%%staffwidth {staff_w_cm}cm\n"
        f"%%scale {scale}\n"
        + _ABC_PAGE_HEADER
    )

    with tempfile.NamedTemporaryFile(suffix='.abc', mode='w', delete=False) as f:
        f.write(header + abc_body)
        abc_path = f.name

    ps_path = abc_path.replace('.abc', '.ps')
    try:
        # abcm2ps exits with rc=1 on mere warnings (e.g. "staffwidth too big")
        # while still writing valid output, so we check for the output file
        # rather than the exit code.
        subprocess.run(
            ['abcm2ps', abc_path, '-O', ps_path, '-q'],
            capture_output=True,
        )
        if not os.path.exists(ps_path):
            raise RuntimeError(f"abcm2ps produced no output for {abc_path}")
        subprocess.run(
            ['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET',
             '-dFirstPage=2', '-dLastPage=2',
             '-sDEVICE=pngalpha', f'-r{resolution}',
             f'-sOutputFile={output_png}', ps_path],
            check=True, capture_output=True,
        )
    finally:
        os.unlink(abc_path)
        if os.path.exists(ps_path):
            os.unlink(ps_path)


def crop_image(img, pad=4):
    """Crop whitespace from a PIL Image, returning the trimmed Image."""
    w, h = img.size

    def is_white_row(y):
        return all(_is_white(img.getpixel((x, y))) for x in range(w))

    def is_white_col(x):
        return all(_is_white(img.getpixel((x, y))) for y in range(h))

    top = 0
    while top < h and is_white_row(top):
        top += 1
    bottom = h - 1
    while bottom > 0 and is_white_row(bottom):
        bottom -= 1
    left = 0
    while left < w and is_white_col(left):
        left += 1
    right = w - 1
    while right > 0 and is_white_col(right):
        right -= 1

    top    = max(0,     top    - pad)
    left   = max(0,     left   - pad)
    bottom = min(h - 1, bottom + pad)
    right  = min(w - 1, right  + pad)

    return img.crop((left, top, right + 1, bottom + 1))


def _is_white(px):
    if isinstance(px, int):
        return px > 240
    return all(c > 240 for c in px[:3])


def make_blank_stave(answer_img_path, output_path):
    """
    Derive a blank stave PNG from an answer stave PNG.

    Detects the end of the treble clef / key signature region by finding the
    first significant gap (≥15 consecutive blank columns) after the clef, then
    whites out all non-staff-line pixels to the right of that gap.  This works
    regardless of stave width — short chord staves and wide scale staves alike.
    """
    img = Image.open(answer_img_path).convert('RGB')
    pixels = img.load()
    w, h = img.size

    # Identify staff line rows: rows where >35% of pixels are dark
    staff_rows = set()
    for y in range(h):
        dark = sum(1 for x in range(w) if pixels[x, y][0] < 80)
        if dark > w * 0.35:
            staff_rows.add(y)

    # Find the first long gap after the treble clef to locate where notes begin.
    # A "gap column" has no non-staff-line dark pixels.
    GAP_THRESHOLD = 15   # consecutive blank columns = end of clef/keysig
    MIN_CLEF_WIDTH = int(w * 0.08)   # clef is never less than 8% of image width

    gap_start = None
    gap_len   = 0
    note_start = int(w * 0.20)  # fallback if gap detection fails

    for x in range(MIN_CLEF_WIDTH, w):
        non_staff = sum(1 for y in range(h)
                        if y not in staff_rows and pixels[x, y][0] < 80)
        if non_staff == 0:
            if gap_start is None:
                gap_start = x
            gap_len += 1
            if gap_len >= GAP_THRESHOLD:
                # Gap found — protect everything up to where gap started
                note_start = gap_start
                break
        else:
            gap_start = None
            gap_len   = 0

    result = img.copy()
    rp = result.load()
    for x in range(note_start, w):
        for y in range(h):
            if y not in staff_rows:
                rp[x, y] = (255, 255, 255)

    result.save(output_path)


# ---------------------------------------------------------------------------
# ReportLab helpers
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MARGIN_X      = 15 * mm
MARGIN_TOP    = 22 * mm
MARGIN_BOTTOM = 15 * mm


def draw_page_header(canvas, title, subtitle=None, show_name_line=True):
    """Draw the standard worksheet title block at the top of the current page."""
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN_TOP + 5 * mm, title)

    if subtitle:
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN_TOP - 2 * mm, subtitle)

    if show_name_line:
        canvas.setFont("Helvetica", 9)
        canvas.drawString(
            MARGIN_X, PAGE_H - MARGIN_TOP - 9 * mm,
            "Name: ________________________________    Date: ____________    Score:  ____ / 20"
        )

    # Divider
    canvas.setLineWidth(0.5)
    canvas.setStrokeColor(colors.black)
    y = PAGE_H - MARGIN_TOP - 13 * mm
    canvas.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)

    return y  # returns y position of divider so caller knows where content starts


def embed_image(canvas, img_path, box_x, box_y, box_w, box_h, align='left'):
    """
    Crop whitespace from img_path and draw it scaled to fit inside the given box.
    Returns (draw_x, draw_y, draw_w, draw_h) of the placed image.
    """
    img = Image.open(img_path)
    cropped = crop_image(img)

    tmp = img_path.replace('.png', '_crop.png')
    cropped.save(tmp)

    # Scale to fit, preserving aspect ratio
    scale = min(box_w / cropped.width * 72,
                box_h / cropped.height * 72)
    draw_w = cropped.width  * scale / 72
    draw_h = cropped.height * scale / 72

    if align == 'centre':
        draw_x = box_x + (box_w - draw_w) / 2
    else:
        draw_x = box_x

    draw_y = box_y + (box_h - draw_h) / 2  # vertically centred in box

    canvas.drawImage(tmp, draw_x, draw_y, width=draw_w, height=draw_h)
    return draw_x, draw_y, draw_w, draw_h


def draw_footer(canvas, text):
    """Draw a small grey footer centred at the bottom of the current page."""
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.Color(0.5, 0.5, 0.5))
    canvas.drawCentredString(PAGE_W / 2, MARGIN_BOTTOM / 2, text)
    canvas.setFillColor(colors.black)
