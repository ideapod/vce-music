#!/usr/bin/env python3
"""
VCE Music Unit 1 – Intervals Worksheet Generator
Generates a printable PDF with 20 interval identification questions.

Usage:
    python3 generate_intervals_worksheet.py              # worksheet only
    python3 generate_intervals_worksheet.py --answers    # also produces answer key
    python3 generate_intervals_worksheet.py --seed 99    # different random set
"""

import os
import sys
import random
import subprocess
import tempfile
from pathlib import Path
from PIL import Image

OUTPUT_FILE = "intervals_worksheet.pdf"
ANSWER_FILE = "intervals_worksheet_ANSWERS.pdf"

# ---------------------------------------------------------------------------
# Music theory
# ---------------------------------------------------------------------------

DIATONIC = ['C', 'D', 'E', 'F', 'G', 'A', 'B']

# Semitones from C for each white key
WHITE_KEY_SEMITONES = [0, 2, 4, 5, 7, 9, 11]

def diatonic_idx(note_name):
    base = note_name.replace('#', '').replace('b', '')
    return DIATONIC.index(base)

def note_semitone(note_name):
    """Semitones above C for the given note name (may include # or b)."""
    base = note_name.replace('#', '').replace('b', '')
    s = WHITE_KEY_SEMITONES[DIATONIC.index(base)]
    if '#' in note_name:
        s += 1
    elif 'b' in note_name:
        s -= 1
    return s

def note_midi(note_name, octave):
    return 12 * (octave + 1) + note_semitone(note_name)

# ABC notation for notes (name, octave) -> ABC string
def abc_note(name, octave, duration='1', accidental=None):
    """
    Return ABC notation for a note.
    In ABC: C4=C, D4=D, ..., B4=B, C5=c, ..., B5=b, C6=c', etc.
    """
    base = name.replace('#', '').replace('b', '')
    acc_str = ''
    if accidental == 'sharp':
        acc_str = '^'
    elif accidental == 'flat':
        acc_str = '_'
    elif accidental == 'natural':
        acc_str = '='

    if octave <= 4:
        # C4 and below: uppercase, with commas for lower octaves
        letter = base.upper()
        commas = ',' * (4 - octave)
        return f"{acc_str}{letter}{commas}{duration}"
    else:
        # C5 and above: lowercase, with apostrophes for higher octaves
        letter = base.lower()
        apostrophes = "'" * (octave - 5)
        return f"{acc_str}{letter}{apostrophes}{duration}"

# Interval definitions: (semitones, diatonic_steps, label)
VCE_INTERVALS = [
    (2,  1, "Major 2nd"),
    (3,  2, "Minor 3rd"),
    (4,  2, "Major 3rd"),
    (5,  3, "Perfect 4th"),
    (6,  3, "Augmented 4th"),
    (6,  4, "Diminished 5th"),
    (7,  4, "Perfect 5th"),
    (8,  5, "Minor 6th"),
    (9,  5, "Major 6th"),
    (10, 6, "Minor 7th"),
    (11, 6, "Major 7th"),
    (12, 7, "Perfect Octave"),
]

# Base notes: (name, octave) — comfortable treble range C4–E5
BASE_NOTES = [
    ('C', 4), ('D', 4), ('E', 4), ('F', 4), ('G', 4),
    ('A', 4), ('B', 4), ('C', 5), ('D', 5), ('E', 5),
]

def compute_upper_note(lower_name, lower_octave, semitones, diatonic_steps):
    """
    Given a lower note and interval, return (upper_name, upper_octave, accidental) or None.
    accidental: None | 'sharp' | 'flat'
    """
    lower_di = diatonic_idx(lower_name)
    upper_di = (lower_di + diatonic_steps) % 7
    octave_bump = (lower_di + diatonic_steps) // 7
    upper_octave = lower_octave + octave_bump
    upper_base = DIATONIC[upper_di]

    # Expected semitone count (relative to C0)
    lower_midi = note_midi(lower_name, lower_octave)
    upper_white_midi = note_midi(upper_base, upper_octave)
    diff = lower_midi + semitones - upper_white_midi

    if diff == 0:
        accidental = None
    elif diff == 1:
        accidental = 'sharp'
    elif diff == -1:
        accidental = 'flat'
    else:
        return None  # double accidental — skip

    # Keep within printable range (no more than 2 ledger lines above staff)
    if upper_octave > 5 or (upper_octave == 5 and upper_di > 4):  # above A5
        return None

    return (upper_base, upper_octave, accidental)

def build_questions(n=20, seed=42):
    rng = random.Random(seed)
    questions = []
    # Ensure all interval types appear at least once (12 types, 20 questions)
    required = list(VCE_INTERVALS)
    rng.shuffle(required)
    pool = required + rng.choices(VCE_INTERVALS, k=n)

    attempts = 0
    idx = 0
    while len(questions) < n and attempts < 2000:
        attempts += 1
        interval = pool[idx % len(pool)]
        idx += 1
        semitones, diatonic_steps, label = interval
        lower_name, lower_octave = rng.choice(BASE_NOTES)

        result = compute_upper_note(lower_name, lower_octave, semitones, diatonic_steps)
        if result is None:
            continue

        upper_name, upper_octave, accidental = result
        questions.append({
            'label': label,
            'lower_name': lower_name,
            'lower_octave': lower_octave,
            'upper_name': upper_name,
            'upper_octave': upper_octave,
            'accidental': accidental,
        })

    return questions[:n]

# ---------------------------------------------------------------------------
# ABC notation generation
# ---------------------------------------------------------------------------

ABC_HEADER = """\
%%pagewidth 12cm
%%pageheight 5cm
%%topmargin 0.2cm
%%botmargin 0.2cm
%%leftmargin 0.4cm
%%rightmargin 0.2cm
%%staffwidth 9cm
%%scale 1.3
%%writefields T 0
"""

def make_abc(q_num, question):
    lower = abc_note(question['lower_name'], question['lower_octave'], duration='2')
    upper_acc = question['accidental']
    upper = abc_note(question['upper_name'], question['upper_octave'],
                     duration='2', accidental=upper_acc)
    # No title — abcm2ps always puts music on page 2; title drawn by ReportLab
    return f"""\
X:{q_num}
M:none
L:1/4
K:C
{lower} {upper} |]
"""

def render_question_png(abc_text, output_png, resolution=200):
    """Render ABC notation to a PNG via abcm2ps + ghostscript."""
    with tempfile.NamedTemporaryFile(suffix='.abc', mode='w', delete=False) as f:
        # Write header + question
        f.write(ABC_HEADER + abc_text)
        abc_path = f.name

    ps_path = abc_path.replace('.abc', '.ps')

    try:
        subprocess.run(
            ['abcm2ps', abc_path, '-O', ps_path, '-q'],
            check=True, capture_output=True
        )
        # abcm2ps always outputs page 1 = blank, page 2 = music; grab page 2
        subprocess.run(
            ['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET',
             '-dFirstPage=2', '-dLastPage=2',
             '-sDEVICE=pngalpha', f'-r{resolution}',
             f'-sOutputFile={output_png}', ps_path],
            check=True, capture_output=True
        )
    finally:
        os.unlink(abc_path)
        if os.path.exists(ps_path):
            os.unlink(ps_path)

# ---------------------------------------------------------------------------
# PDF assembly with ReportLab
# ---------------------------------------------------------------------------

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import mm

def assemble_pdf(questions, question_images, output_path, include_answers=False):
    """Compose the final PDF from rendered question images."""
    page_w, page_h = A4
    c = rl_canvas.Canvas(output_path, pagesize=A4)

    margin_x = 15 * mm
    margin_top = 22 * mm
    margin_bottom = 15 * mm

    # --- Header ---
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(page_w / 2, page_h - margin_top + 5 * mm,
                        "VCE Music – Unit 1: Interval Identification")

    c.setFont("Helvetica", 9)
    c.drawCentredString(page_w / 2, page_h - margin_top - 2 * mm,
                        "Identify each interval and write your answer on the line below each example.")

    c.setFont("Helvetica", 9)
    c.drawString(margin_x, page_h - margin_top - 9 * mm,
                 "Name: ________________________________    Date: ____________    Score:  ____ / 20")

    # Divider line
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.black)
    c.line(margin_x, page_h - margin_top - 13 * mm,
           page_w - margin_x, page_h - margin_top - 13 * mm)

    # --- Layout: 2 columns x 10 rows ---
    n_cols = 2
    n_rows = 10
    usable_w = page_w - 2 * margin_x
    usable_h = page_h - margin_top - 18 * mm - margin_bottom
    col_w = usable_w / n_cols
    row_h = usable_h / n_rows

    for i, (q, img_path) in enumerate(zip(questions, question_images)):
        col = i % n_cols
        row = i // n_cols

        box_x = margin_x + col * col_w
        box_y = page_h - margin_top - 18 * mm - (row + 1) * row_h

        # Load and scale the image to fit the box
        img = Image.open(img_path)
        # Crop to content (remove whitespace)
        bbox = img.convert('RGBA')
        # Find non-white bounding box
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        diff = Image.new('RGBA', img.size)
        for x in range(img.width):
            for y in range(img.height):
                px = img.getpixel((x, y))
                if isinstance(px, int):
                    px = (px, px, px, 255)
                elif len(px) == 3:
                    px = px + (255,)
                if px[:3] != (255, 255, 255):
                    diff.putpixel((x, y), (0, 0, 0, 255))

        # Simple crop: find min/max non-white rows/cols
        arr = list(img.getdata())
        w, h = img.size
        def is_white(px):
            if isinstance(px, int):
                return px > 240
            return all(c > 240 for c in px[:3])

        top = 0
        while top < h and all(is_white(img.getpixel((x, top))) for x in range(w)):
            top += 1
        bottom = h - 1
        while bottom > 0 and all(is_white(img.getpixel((x, bottom))) for x in range(w)):
            bottom -= 1
        left = 0
        while left < w and all(is_white(img.getpixel((left, y))) for y in range(h)):
            left += 1
        right = w - 1
        while right > 0 and all(is_white(img.getpixel((right, y))) for y in range(h)):
            right -= 1

        crop_pad = 4
        top = max(0, top - crop_pad)
        left = max(0, left - crop_pad)
        bottom = min(h - 1, bottom + crop_pad)
        right = min(w - 1, right + crop_pad)

        img_cropped = img.crop((left, top, right + 1, bottom + 1))

        # Scale to fit the available height, leaving room for answer line
        available_h = row_h - 10 * mm  # leave space for answer line
        available_w = col_w - 4 * mm
        scale = min(available_w / img_cropped.width * 72,
                    available_h / img_cropped.height * 72)
        draw_w = img_cropped.width * scale / 72
        draw_h = img_cropped.height * scale / 72

        img_y = box_y + row_h - draw_h - 2 * mm

        # Save cropped image to temp file for ReportLab
        tmp_img = img_path.replace('.png', '_crop.png')
        img_cropped.save(tmp_img)

        c.drawImage(tmp_img, box_x + 2 * mm, img_y, width=draw_w, height=draw_h)

        # Question number label (top-left of box)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.black)
        c.drawString(box_x + 2 * mm, box_y + row_h - 4 * mm, f"Q{i + 1}.")

        # Answer line
        ans_y = box_y + 4 * mm
        c.setLineWidth(0.5)
        c.setStrokeColor(colors.black)
        c.line(box_x + 14 * mm, ans_y, box_x + col_w - 4 * mm, ans_y)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.Color(0.4, 0.4, 0.4))
        c.drawString(box_x + 2 * mm, ans_y - 0.5 * mm, "Interval:")
        c.setFillColor(colors.black)

        # Answer (if answer key mode)
        if include_answers:
            c.setFont("Helvetica-BoldOblique", 8.5)
            c.setFillColor(colors.Color(0.7, 0, 0))
            c.drawString(box_x + 8 * mm, ans_y + 1 * mm, q['label'])
            c.setFillColor(colors.black)

    # --- Footer ---
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.Color(0.5, 0.5, 0.5))
    label = "ANSWER KEY" if include_answers else "VCE Music Unit 1 | Intervals Worksheet"
    c.drawCentredString(page_w / 2, margin_bottom / 2, label)

    c.save()
    print(f"Saved: {output_path}")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    seed = 42
    include_answers = '--answers' in sys.argv
    for arg in sys.argv[1:]:
        if arg.startswith('--seed='):
            seed = int(arg.split('=')[1])

    print(f"Building {20} interval questions (seed={seed})...")
    questions = build_questions(n=20, seed=seed)

    # Print question summary
    print("\nQuestions:")
    for i, q in enumerate(questions, 1):
        acc = f"({q['accidental']})" if q['accidental'] else ""
        print(f"  Q{i:2d}: {q['lower_name']}{q['lower_octave']} → "
              f"{q['upper_name']}{q['upper_octave']} {acc:8s} = {q['label']}")

    # Render each question to PNG
    tmpdir = tempfile.mkdtemp(prefix='intervals_')
    image_paths = []
    print(f"\nRendering {len(questions)} questions...")

    for i, q in enumerate(questions, 1):
        abc_text = make_abc(i, q)
        png_path = os.path.join(tmpdir, f"q{i:02d}.png")
        render_question_png(abc_text, png_path, resolution=180)
        image_paths.append(png_path)
        print(f"  Q{i:2d} done", end='\r')

    print(f"\nAssembling PDF...")
    assemble_pdf(questions, image_paths, OUTPUT_FILE, include_answers=False)

    if include_answers:
        assemble_pdf(questions, image_paths, ANSWER_FILE, include_answers=True)
        print(f"Answer key: {ANSWER_FILE}")

    # Cleanup temp images
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\nDone! Open {OUTPUT_FILE}")
    subprocess.run(['open', OUTPUT_FILE])

if __name__ == '__main__':
    main()
