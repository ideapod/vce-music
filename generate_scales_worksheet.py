#!/usr/bin/env python3
"""
VCE Music Unit 1 – Scales Worksheet Generator
Generates a 2-page printable PDF: blank staves on page 1, fully written answers on page 2.
Covers all scales from the exam checklist: major, natural minor, major pentatonic,
minor pentatonic — up to 2 sharps and 2 flats.

Usage:
    python3 generate_scales_worksheet.py           # all 20 scales
    python3 generate_scales_worksheet.py --select  # pick a random subset of 10
    python3 generate_scales_worksheet.py --seed=7  # different random subset
"""

import os
import sys
import random
import subprocess
import tempfile
import shutil
import math

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

import music_utils as mu

OUTPUT_FILE = "scales_worksheet.pdf"

# ---------------------------------------------------------------------------
# Scale definitions
#
# 'key'   : ABC K: field (controls key signature shown on stave)
# 'notes' : ABC note string for the answer stave (key sig handles accidentals)
# 'blank' : ABC note string for the question stave (x = invisible note)
#
# In ABC notation:
#   Uppercase = octave 4  (C=C4, B=B4)
#   Lowercase = octave 5  (c=C5, b=B5)
#   Comma     = one octave down  (B, = B3)
#   Key sig handles sharps/flats automatically
# ---------------------------------------------------------------------------

SCALES = [
    # ── Major scales ──────────────────────────────────────────────────────────
    {
        'name': 'C major',
        'key':   'C',
        'notes': 'C D E F G A B c',      # C4 → C5
        'blank': 'x x x x x x x x',
        'type':  'major',
    },
    {
        'name': 'G major',
        'key':   'G',
        'notes': 'G A B c d e f g',      # G4 → G5  (f = F# via key sig)
        'blank': 'x x x x x x x x',
        'type':  'major',
    },
    {
        'name': 'D major',
        'key':   'D',
        'notes': 'D E F G A B c d',      # D4 → D5  (F=F#, c=C# via key sig)
        'blank': 'x x x x x x x x',
        'type':  'major',
    },
    {
        'name': 'F major',
        'key':   'F',
        'notes': 'F G A B c d e f',      # F4 → F5  (B = Bb via key sig)
        'blank': 'x x x x x x x x',
        'type':  'major',
    },
    {
        'name': 'Bb major',
        'key':   'Bb',
        'notes': 'B, C D E F G A B',     # Bb3 → Bb4  (B,E flat via key sig)
        'blank': 'x, x x x x x x x',
        'type':  'major',
    },

    # ── Natural minor scales ──────────────────────────────────────────────────
    {
        'name': 'A natural minor',
        'key':   'Amin',
        'notes': 'A B c d e f g a',      # A4 → A5
        'blank': 'x x x x x x x x',
        'type':  'minor',
    },
    {
        'name': 'E natural minor',
        'key':   'Emin',
        'notes': 'E F G A B c d e',      # E4 → E5  (F = F# via key sig)
        'blank': 'x x x x x x x x',
        'type':  'minor',
    },
    {
        'name': 'B natural minor',
        'key':   'Bmin',
        'notes': 'B, C D E F G A B',     # B3 → B4  (C=C#, F=F# via key sig)
        'blank': 'x, x x x x x x x',
        'type':  'minor',
    },
    {
        'name': 'D natural minor',
        'key':   'Dmin',
        'notes': 'D E F G A B c d',      # D4 → D5  (B = Bb via key sig)
        'blank': 'x x x x x x x x',
        'type':  'minor',
    },
    {
        'name': 'G natural minor',
        'key':   'Gmin',
        'notes': 'G A B c d e f g',      # G4 → G5  (B=Bb, e=Eb via key sig)
        'blank': 'x x x x x x x x',
        'type':  'minor',
    },

    # ── Major pentatonic scales ───────────────────────────────────────────────
    {
        'name': 'C major pentatonic',
        'key':   'C',
        'notes': 'C D E G A c',          # C4 D4 E4 G4 A4 C5
        'blank': 'x x x x x x',
        'type':  'major_pent',
    },
    {
        'name': 'G major pentatonic',
        'key':   'G',
        'notes': 'G A B d e g',          # G4 A4 B4 D5 E5 G5
        'blank': 'x x x x x x',
        'type':  'major_pent',
    },
    {
        'name': 'D major pentatonic',
        'key':   'D',
        'notes': 'D E F A B d',          # D4 E4 F#4 A4 B4 D5
        'blank': 'x x x x x x',
        'type':  'major_pent',
    },
    {
        'name': 'F major pentatonic',
        'key':   'F',
        'notes': 'F G A c d f',          # F4 G4 A4 C5 D5 F5
        'blank': 'x x x x x x',
        'type':  'major_pent',
    },
    {
        'name': 'Bb major pentatonic',
        'key':   'Bb',
        'notes': 'B, C D F G B',         # Bb3 C4 D4 F4 G4 Bb4
        'blank': 'x, x x x x x',
        'type':  'major_pent',
    },

    # ── Minor pentatonic scales ───────────────────────────────────────────────
    {
        'name': 'A minor pentatonic',
        'key':   'Amin',
        'notes': 'A c d e g a',          # A4 C5 D5 E5 G5 A5
        'blank': 'x x x x x x',
        'type':  'minor_pent',
    },
    {
        'name': 'E minor pentatonic',
        'key':   'Emin',
        'notes': 'E G A B d e',          # E4 G4 A4 B4 D5 E5
        'blank': 'x x x x x x',
        'type':  'minor_pent',
    },
    {
        'name': 'B minor pentatonic',
        'key':   'Bmin',
        'notes': 'B, D E F A B',         # B3 D4 E4 F#4 A4 B4
        'blank': 'x, x x x x x',
        'type':  'minor_pent',
    },
    {
        'name': 'D minor pentatonic',
        'key':   'Dmin',
        'notes': 'D F G A c d',          # D4 F4 G4 A4 C5 D5
        'blank': 'x x x x x x',
        'type':  'minor_pent',
    },
    {
        'name': 'G minor pentatonic',
        'key':   'Gmin',
        'notes': 'G B c d f g',          # G4 Bb4 C5 D5 F5 G5
        'blank': 'x x x x x x',
        'type':  'minor_pent',
    },
]

TYPE_LABEL = {
    'major':      'major scale',
    'minor':      'natural minor scale',
    'major_pent': 'major pentatonic scale',
    'minor_pent': 'minor pentatonic scale',
}

# ---------------------------------------------------------------------------
# ABC generation & rendering
# ---------------------------------------------------------------------------

def _make_abc(scale):
    notes = scale['notes']
    return (
        f"X:1\n"
        f"M:none\n"
        f"L:1/4\n"
        f"K:{scale['key']}\n"
        f"{notes} |]\n"
    )

def _render_scale_pair(scale, idx, tmpdir):
    """
    Render the answer stave PNG, then derive a blank stave from it.
    Using the same source image ensures blank/answer staves are identical size.
    """
    # All scales use the same page width — pentatonic notes just space out more
    answer_png = os.path.join(tmpdir, f"s{idx:02d}_answer.png")
    blank_png  = os.path.join(tmpdir, f"s{idx:02d}_blank.png")

    mu.render_abc_to_png(_make_abc(scale), answer_png,
                         page_w_cm=16.0, page_h_cm=3.5,
                         staff_w_cm=13.0, scale=1.15)
    mu.make_blank_stave(answer_png, blank_png)
    return blank_png, answer_png

# ---------------------------------------------------------------------------
# PDF assembly  (2-page: questions then answers)
# ---------------------------------------------------------------------------

SCALES_PER_PAGE = 10   # 2 columns × 5 rows

def _draw_scales_page(canvas, scales, img_paths_list, page_title,
                      use_blank, footer_text):
    """Draw one page worth of scale staves."""
    mu.draw_page_header(canvas, page_title,
                        subtitle=("Write each scale ascending on the stave below."
                                  if use_blank else "Answers"),
                        show_name_line=use_blank)

    n_cols = 2
    n_rows = math.ceil(len(scales) / n_cols)
    usable_w = mu.PAGE_W - 2 * mu.MARGIN_X
    usable_h = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - mu.MARGIN_BOTTOM
    col_w = usable_w / n_cols
    row_h = usable_h / min(n_rows, SCALES_PER_PAGE // n_cols)

    for i, (scale, (blank_png, answer_png)) in enumerate(zip(scales, img_paths_list)):
        col = i % n_cols
        row = i // n_cols
        box_x = mu.MARGIN_X + col * col_w
        box_y = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - (row + 1) * row_h

        img_path = blank_png if use_blank else answer_png

        # Scale name label above the stave
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.setFillColor(colors.black)
        canvas.drawString(box_x + 2 * mm, box_y + row_h - 5 * mm,
                          f"Q{i + 1}.  Write the {scale['name']} scale:")

        # Stave image
        mu.embed_image(canvas, img_path,
                       box_x + 2 * mm, box_y + 3 * mm,
                       col_w - 4 * mm, row_h - 10 * mm)

        # Thin separator between questions
        canvas.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        canvas.setLineWidth(0.3)
        canvas.line(box_x, box_y, box_x + col_w, box_y)

    mu.draw_footer(canvas, footer_text)


def assemble_pdf(scales, img_pairs, output_path):
    """Assemble the final PDF: question pages then answer pages."""
    c = rl_canvas.Canvas(output_path, pagesize=(mu.PAGE_W, mu.PAGE_H))

    # Split into batches of SCALES_PER_PAGE
    def batches(lst):
        for i in range(0, len(lst), SCALES_PER_PAGE):
            yield lst[i:i + SCALES_PER_PAGE]

    scale_batches    = list(batches(scales))
    img_pair_batches = list(batches(img_pairs))

    # --- Question pages ---
    for batch_idx, (scale_batch, img_batch) in enumerate(zip(scale_batches, img_pair_batches)):
        if batch_idx > 0:
            c.showPage()
        _draw_scales_page(c, scale_batch, img_batch,
                          "VCE Music – Unit 1: Scales",
                          use_blank=True,
                          footer_text="VCE Music Unit 1 | Scales Worksheet")

    # --- Answer pages ---
    for batch_idx, (scale_batch, img_batch) in enumerate(zip(scale_batches, img_pair_batches)):
        c.showPage()
        _draw_scales_page(c, scale_batch, img_batch,
                          "VCE Music – Unit 1: Scales  (Answer Key)",
                          use_blank=False,
                          footer_text="ANSWER KEY")

    c.save()
    print(f"Saved: {output_path}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    seed = 42
    select_subset = '--select' in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith('--seed='):
            seed = int(arg.split('=')[1])

    scales = list(SCALES)
    if select_subset:
        rng = random.Random(seed)
        scales = rng.sample(scales, 10)

    print(f"Generating scales worksheet — {len(scales)} scales")
    for s in scales:
        print(f"  {s['name']}")

    tmpdir = tempfile.mkdtemp(prefix='scales_')
    try:
        print(f"\nRendering staves...")
        img_pairs = []
        for i, scale in enumerate(scales, 1):
            blank_png, answer_png = _render_scale_pair(scale, i, tmpdir)
            img_pairs.append((blank_png, answer_png))
            print(f"  {i:2d}/{len(scales)}  {scale['name']}", end='\r')
        print()

        print("Assembling PDF...")
        assemble_pdf(scales, img_pairs, OUTPUT_FILE)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\nDone! {len(scales)} scales, "
          f"{math.ceil(len(scales)/SCALES_PER_PAGE) * 2} pages total.")
    subprocess.run(['open', OUTPUT_FILE])

if __name__ == '__main__':
    main()
