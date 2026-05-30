#!/usr/bin/env python3
"""
VCE Music Unit 1 – Intervals Worksheet Generator
Generates a printable PDF with 20 interval identification questions on treble clef staves.

Usage:
    python3 generate_intervals_worksheet.py              # worksheet only
    python3 generate_intervals_worksheet.py --answers    # also produces answer key
    python3 generate_intervals_worksheet.py --seed=99    # different random question set
"""

import os
import sys
import random
import subprocess
import tempfile
import shutil

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

import music_utils as mu

OUTPUT_FILE = "intervals_worksheet.pdf"
ANSWER_FILE = "intervals_worksheet_ANSWERS.pdf"

# ---------------------------------------------------------------------------
# Music theory
# ---------------------------------------------------------------------------

DIATONIC = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
WHITE_KEY_SEMITONES = [0, 2, 4, 5, 7, 9, 11]

def _diatonic_idx(note_name):
    return DIATONIC.index(note_name.replace('#', '').replace('b', ''))

def _note_midi(note_name, octave):
    base = note_name.replace('#', '').replace('b', '')
    s = WHITE_KEY_SEMITONES[DIATONIC.index(base)]
    if '#' in note_name: s += 1
    elif 'b' in note_name: s -= 1
    return 12 * (octave + 1) + s

def _abc_note(name, octave, duration='2', accidental=None):
    """Convert (name, octave, accidental) to ABC notation string."""
    base = name.replace('#', '').replace('b', '')
    acc = {None: '', 'sharp': '^', 'flat': '_', 'natural': '='}.get(accidental, '')
    if octave <= 4:
        return f"{acc}{base.upper()}{',' * (4 - octave)}{duration}"
    else:
        apos = "'" * (octave - 5)
        return f"{acc}{base.lower()}{apos}{duration}"

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

BASE_NOTES = [
    ('C', 4), ('D', 4), ('E', 4), ('F', 4), ('G', 4),
    ('A', 4), ('B', 4), ('C', 5), ('D', 5), ('E', 5),
]

def _compute_upper_note(lower_name, lower_octave, semitones, diatonic_steps):
    lower_di  = _diatonic_idx(lower_name)
    upper_di  = (lower_di + diatonic_steps) % 7
    upper_oct = lower_octave + (lower_di + diatonic_steps) // 7
    upper_base = DIATONIC[upper_di]
    diff = _note_midi(lower_name, lower_octave) + semitones - _note_midi(upper_base, upper_oct)
    if diff == 1:   acc = 'sharp'
    elif diff == -1: acc = 'flat'
    elif diff == 0:  acc = None
    else:            return None
    if upper_oct > 5 or (upper_oct == 5 and upper_di > 4):
        return None
    return (upper_base, upper_oct, acc)

def build_questions(n=20, seed=42):
    rng = random.Random(seed)
    questions = []
    pool = list(VCE_INTERVALS) * 3
    rng.shuffle(pool)
    idx = 0
    attempts = 0
    while len(questions) < n and attempts < 2000:
        attempts += 1
        semitones, diatonic_steps, label = pool[idx % len(pool)]
        idx += 1
        lower_name, lower_octave = rng.choice(BASE_NOTES)
        result = _compute_upper_note(lower_name, lower_octave, semitones, diatonic_steps)
        if result is None:
            continue
        upper_name, upper_octave, accidental = result
        questions.append({
            'label': label,
            'lower_name': lower_name, 'lower_octave': lower_octave,
            'upper_name': upper_name, 'upper_octave': upper_octave,
            'accidental': accidental,
        })
    return questions[:n]

# ---------------------------------------------------------------------------
# ABC generation & rendering
# ---------------------------------------------------------------------------

def _make_abc(q_num, q):
    lower = _abc_note(q['lower_name'], q['lower_octave'])
    upper = _abc_note(q['upper_name'], q['upper_octave'], accidental=q['accidental'])
    return f"X:{q_num}\nM:none\nL:1/4\nK:C\n{lower} {upper} |]\n"

def _render_questions(questions, tmpdir):
    paths = []
    for i, q in enumerate(questions, 1):
        png = os.path.join(tmpdir, f"q{i:02d}.png")
        mu.render_abc_to_png(_make_abc(i, q), png,
                             page_w_cm=10, page_h_cm=3.5,
                             staff_w_cm=8.5, scale=1.2)
        paths.append(png)
        print(f"  Q{i:2d} done", end='\r')
    print()
    return paths

# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------

def _assemble_pdf(questions, img_paths, output_path, include_answers=False):
    c = rl_canvas.Canvas(output_path, pagesize=(mu.PAGE_W, mu.PAGE_H))

    subtitle = ("Identify each interval and write your answer on the line below."
                if not include_answers else "Answer Key")
    mu.draw_page_header(c, "VCE Music – Unit 1: Interval Identification",
                        subtitle=subtitle, show_name_line=not include_answers)

    n_cols, n_rows = 2, 10
    usable_w = mu.PAGE_W - 2 * mu.MARGIN_X
    usable_h = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - mu.MARGIN_BOTTOM
    col_w = usable_w / n_cols
    row_h = usable_h / n_rows

    for i, (q, img_path) in enumerate(zip(questions, img_paths)):
        col = i % n_cols
        row = i // n_cols
        box_x = mu.MARGIN_X + col * col_w
        box_y = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - (row + 1) * row_h

        # Stave image — leave 9mm at bottom for the answer line area
        mu.embed_image(c, img_path,
                       box_x + 2 * mm, box_y + 9 * mm,
                       col_w - 4 * mm, row_h - 11 * mm)

        # Question number
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

        if include_answers:
            c.setFont("Helvetica-BoldOblique", 8.5)
            c.setFillColor(colors.Color(0.7, 0, 0))
            c.drawString(box_x + 14 * mm, ans_y + 1 * mm, q['label'])
            c.setFillColor(colors.black)

    mu.draw_footer(c, "ANSWER KEY" if include_answers
                   else "VCE Music Unit 1 | Intervals Worksheet")
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

    print(f"Building 20 interval questions (seed={seed})...")
    questions = build_questions(n=20, seed=seed)
    for i, q in enumerate(questions, 1):
        acc = f"({q['accidental']})" if q['accidental'] else ""
        print(f"  Q{i:2d}: {q['lower_name']}{q['lower_octave']} → "
              f"{q['upper_name']}{q['upper_octave']} {acc:8s} = {q['label']}")

    tmpdir = tempfile.mkdtemp(prefix='intervals_')
    try:
        print(f"\nRendering {len(questions)} staves...")
        img_paths = _render_questions(questions, tmpdir)

        print("Assembling worksheet PDF...")
        _assemble_pdf(questions, img_paths, OUTPUT_FILE, include_answers=False)

        if include_answers:
            print("Assembling answer key PDF...")
            _assemble_pdf(questions, img_paths, ANSWER_FILE, include_answers=True)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    subprocess.run(['open', OUTPUT_FILE])

if __name__ == '__main__':
    main()
