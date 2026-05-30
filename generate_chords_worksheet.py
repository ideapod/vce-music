#!/usr/bin/env python3
"""
VCE Music Unit 1 – Chords Worksheets Generator

Generates two 2-page PDFs:
  chords_write_worksheet.pdf    — named chord prompt + blank stave (answer page follows)
  chords_identify_worksheet.pdf — chord shown on stave, student writes the name below

Usage:
    python3 generate_chords_worksheet.py
    python3 generate_chords_worksheet.py --seed=99
"""

import os, sys, random, subprocess, tempfile, shutil, math

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

import music_utils as mu

WRITE_PDF    = "chords_write_worksheet.pdf"
IDENTIFY_PDF = "chords_identify_worksheet.pdf"

# ---------------------------------------------------------------------------
# Chord definitions
#
# 'write_abc'   : ABC chord bracket in K:C with explicit accidentals (answer stave)
# 'id_key'      : K: field for the identify worksheet (key sig shown to student)
# 'id_abc'      : ABC chord bracket in that key (accidentals handled by key sig)
#
# All chords are root-position triads in a comfortable treble range (C4–D5).
# ABC note bracket syntax: [CEG] = C E G played simultaneously (block chord).
# Duration 4 = whole note (with L:1/4).
# ---------------------------------------------------------------------------

CHORDS = [
    # ── Major ─────────────────────────────────────────────────────────────
    {'name': 'C major',  'type': 'major',
     'write_abc': '[CEG]4',   'id_key': 'C',  'id_abc': '[CEG]4'},
    {'name': 'G major',  'type': 'major',
     'write_abc': '[GBd]4',   'id_key': 'G',  'id_abc': '[GBd]4'},   # K:G → f=F#; G B D5
    {'name': 'D major',  'type': 'major',
     'write_abc': '[D^FA]4',  'id_key': 'D',  'id_abc': '[DFA]4'},   # K:D → F=F#, A natural
    {'name': 'F major',  'type': 'major',
     'write_abc': '[FAc]4',   'id_key': 'F',  'id_abc': '[FAc]4'},   # K:F → B=Bb (unused here)
    {'name': 'Bb major', 'type': 'major',
     'write_abc': '[_BDF]4',  'id_key': 'Bb', 'id_abc': '[BDF]4'},   # K:Bb → B=Bb

    # ── Minor ─────────────────────────────────────────────────────────────
    {'name': 'A minor',  'type': 'minor',
     'write_abc': '[ACE]4',   'id_key': 'Am', 'id_abc': '[ACE]4'},
    {'name': 'E minor',  'type': 'minor',
     'write_abc': '[EGB]4',   'id_key': 'Em', 'id_abc': '[EGB]4'},
    {'name': 'D minor',  'type': 'minor',
     'write_abc': '[DFA]4',   'id_key': 'Dm', 'id_abc': '[DFA]4'},   # K:Dm(=K:F) → D F A
    {'name': 'G minor',  'type': 'minor',
     'write_abc': '[G_Bd]4',  'id_key': 'Gm', 'id_abc': '[GBd]4'},   # K:Gm(=K:Bb) → B=Bb
    {'name': 'B minor',  'type': 'minor',
     'write_abc': '[BD^F]4',  'id_key': 'Bm', 'id_abc': '[BDF]4'},   # K:Bm(=K:D) → F=F#

    # ── Diminished ────────────────────────────────────────────────────────
    {'name': 'B diminished',  'type': 'dim',
     'write_abc': '[BDF]4',   'id_key': 'C',  'id_abc': '[BDF]4'},   # B D F — all naturals
    {'name': 'E diminished',  'type': 'dim',
     'write_abc': '[EG_B]4',  'id_key': 'F',  'id_abc': '[EGB]4'},   # K:F → B=Bb → E G Bb
    {'name': 'A diminished',  'type': 'dim',
     'write_abc': '[AC_E]4',  'id_key': 'Bb', 'id_abc': '[ACE]4'},   # K:Bb → E=Eb → A C Eb
    {'name': 'F# diminished', 'type': 'dim',
     'write_abc': '[^FAC]4',  'id_key': 'G',  'id_abc': '[FAC]4'},   # K:G → F=F# → F# A C
    {'name': 'C# diminished', 'type': 'dim',
     'write_abc': '[^CEG]4',  'id_key': 'D',  'id_abc': '[CEG]4'},   # K:D → C=C# → C# E G

    # ── Augmented ─────────────────────────────────────────────────────────
    {'name': 'C augmented',  'type': 'aug',
     'write_abc': '[CE^G]4',  'id_key': 'C',  'id_abc': '[CE^G]4'},  # C E G#
    {'name': 'F augmented',  'type': 'aug',
     'write_abc': '[FA^c]4',  'id_key': 'F',  'id_abc': '[FA^c]4'},  # F A C#
    {'name': 'G augmented',  'type': 'aug',
     'write_abc': '[GB^d]4',  'id_key': 'G',  'id_abc': '[GB^d]4'},  # G B D#
    {'name': 'Bb augmented', 'type': 'aug',
     'write_abc': '[_BD^F]4', 'id_key': 'Bb', 'id_abc': '[BD^F]4'}, # Bb D F#
    {'name': 'D augmented',  'type': 'aug',
     'write_abc': '[D^F^A]4', 'id_key': 'D',  'id_abc': '[DF^A]4'}, # D F# A#  (K:D→F=F#, explicit ^A)
]

TYPE_LABEL = {
    'major': 'major',
    'minor': 'minor',
    'dim':   'diminished',
    'aug':   'augmented',
}

# ---------------------------------------------------------------------------
# ABC rendering
# ---------------------------------------------------------------------------

# Render chords on a wide stave so the 22% clef-protection zone in
# make_blank_stave() sits well clear of the chord noteheads.
_CHORD_PAGE_W  = 12.0
_CHORD_PAGE_H  = 3.8
_CHORD_STAFF_W = 9.5

def _make_chord_abc(abc_chord, key='C'):
    return (
        f"X:1\nM:none\nL:1/4\nK:{key}\n"
        f"{abc_chord} |]\n"
    )

def _render_chord_pair(chord, idx, tmpdir):
    """
    Render the answer stave at normal width, then derive a blank stave from a
    separately rendered wide version (22cm).  The wide render puts the chord
    note at ~5% of the image so the gap-detection in make_blank_stave reliably
    finds the clef boundary.  The cropped blank stave looks identical to the
    scale/interval blank staves: treble clef + full-width staff lines.
    """
    answer_png    = os.path.join(tmpdir, f"c{idx:02d}_answer.png")
    blank_src_png = os.path.join(tmpdir, f"c{idx:02d}_blank_src.png")
    blank_png     = os.path.join(tmpdir, f"c{idx:02d}_blank.png")

    mu.render_abc_to_png(
        _make_chord_abc(chord['write_abc'], key='C'),
        answer_png,
        page_w_cm=_CHORD_PAGE_W, page_h_cm=_CHORD_PAGE_H,
        staff_w_cm=_CHORD_STAFF_W, scale=1.2,
    )
    mu.render_abc_to_png(
        _make_chord_abc(chord['write_abc'], key='C'),
        blank_src_png,
        page_w_cm=22.0, page_h_cm=_CHORD_PAGE_H,
        staff_w_cm=20.0, scale=1.2,
    )
    mu.make_blank_stave(blank_src_png, blank_png)
    return blank_png, answer_png

def _render_identify_stave(chord, idx, tmpdir):
    """Render the chord with its key signature for the identify worksheet."""
    png = os.path.join(tmpdir, f"c{idx:02d}_id.png")
    mu.render_abc_to_png(
        _make_chord_abc(chord['id_abc'], key=chord['id_key']),
        png,
        page_w_cm=_CHORD_PAGE_W, page_h_cm=_CHORD_PAGE_H,
        staff_w_cm=_CHORD_STAFF_W, scale=1.2,
    )
    return png

# ---------------------------------------------------------------------------
# PDF assembly — shared layout: 3 columns × 5 rows = 15 questions per page
# ---------------------------------------------------------------------------

N_COLS = 3
N_ROWS = 5

def _page_layout():
    usable_w = mu.PAGE_W - 2 * mu.MARGIN_X
    usable_h = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - mu.MARGIN_BOTTOM
    col_w = usable_w / N_COLS
    row_h = usable_h / N_ROWS
    return col_w, row_h

def _draw_chord_page(canvas, questions, img_fn, label_fn,
                     page_title, subtitle, show_name_line, footer):
    """
    Draw one page of chord questions.
    img_fn(q, i)   -> path to the stave PNG for question i
    label_fn(q, i) -> text drawn above the stave
    """
    mu.draw_page_header(canvas, page_title, subtitle=subtitle,
                        show_name_line=show_name_line)

    col_w, row_h = _page_layout()

    for i, q in enumerate(questions):
        col = i % N_COLS
        row = i // N_COLS
        box_x = mu.MARGIN_X + col * col_w
        box_y  = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - (row + 1) * row_h

        # Label above stave
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.black)
        canvas.drawString(box_x + 2 * mm, box_y + row_h - 5 * mm,
                          label_fn(q, i))

        # Stave image
        img_path = img_fn(q, i)
        mu.embed_image(canvas, img_path,
                       box_x + 1 * mm, box_y + 8 * mm,
                       col_w - 2 * mm, row_h - 14 * mm)

        # Separator
        canvas.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        canvas.setLineWidth(0.3)
        canvas.line(box_x, box_y, box_x + col_w, box_y)

    mu.draw_footer(canvas, footer)


# ---------------------------------------------------------------------------
# Worksheet 1: Write the chord
# ---------------------------------------------------------------------------

def build_write_pdf(questions, img_pairs, output_path):
    c = rl_canvas.Canvas(output_path, pagesize=(mu.PAGE_W, mu.PAGE_H))

    # Page 1 — blank staves with prompt
    _draw_chord_page(
        c, questions,
        img_fn    = lambda q, i: img_pairs[i][0],   # blank
        label_fn  = lambda q, i: f"Q{i+1}.  Write a {q['name']} chord:",
        page_title   = "VCE Music – Unit 1: Write the Chord",
        subtitle     = "Write the named chord as a block chord in root position.",
        show_name_line = True,
        footer       = "VCE Music Unit 1 | Chords – Write",
    )

    # Page 2 — answer staves
    c.showPage()
    _draw_chord_page(
        c, questions,
        img_fn    = lambda q, i: img_pairs[i][1],   # answer
        label_fn  = lambda q, i: f"Q{i+1}.  {q['name']}",
        page_title   = "VCE Music – Unit 1: Write the Chord  (Answer Key)",
        subtitle     = "Answers",
        show_name_line = False,
        footer       = "ANSWER KEY",
    )

    c.save()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Worksheet 2: Identify the chord
# ---------------------------------------------------------------------------

def build_identify_pdf(questions, id_imgs, output_path):
    c = rl_canvas.Canvas(output_path, pagesize=(mu.PAGE_W, mu.PAGE_H))

    col_w, row_h = _page_layout()

    # Page 1 — chord shown, student writes name on answer line
    mu.draw_page_header(c, "VCE Music – Unit 1: Name the Chord",
                        subtitle="Write the name of each chord (e.g. G minor, D augmented).",
                        show_name_line=True)

    for i, (q, img_path) in enumerate(zip(questions, id_imgs)):
        col = i % N_COLS
        row = i // N_COLS
        box_x = mu.MARGIN_X + col * col_w
        box_y  = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - (row + 1) * row_h

        # Question number
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawString(box_x + 2 * mm, box_y + row_h - 5 * mm, f"Q{i+1}.")

        # Stave with chord
        mu.embed_image(c, img_path,
                       box_x + 1 * mm, box_y + 11 * mm,
                       col_w - 2 * mm, row_h - 17 * mm)

        # Answer line
        ans_y = box_y + 5 * mm
        c.setLineWidth(0.5)
        c.setStrokeColor(colors.black)
        c.line(box_x + 10 * mm, ans_y, box_x + col_w - 2 * mm, ans_y)
        c.setFont("Helvetica", 7)
        c.setFillColor(colors.Color(0.4, 0.4, 0.4))
        c.drawString(box_x + 2 * mm, ans_y - 0.5 * mm, "Chord:")
        c.setFillColor(colors.black)

        # Separator
        c.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        c.setLineWidth(0.3)
        c.line(box_x, box_y, box_x + col_w, box_y)

    mu.draw_footer(c, "VCE Music Unit 1 | Chords – Identify")

    # Page 2 — answers
    c.showPage()
    mu.draw_page_header(c, "VCE Music – Unit 1: Name the Chord  (Answer Key)",
                        subtitle="Answers", show_name_line=False)

    for i, (q, img_path) in enumerate(zip(questions, id_imgs)):
        col = i % N_COLS
        row = i // N_COLS
        box_x = mu.MARGIN_X + col * col_w
        box_y  = mu.PAGE_H - mu.MARGIN_TOP - 18 * mm - (row + 1) * row_h

        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(colors.black)
        c.drawString(box_x + 2 * mm, box_y + row_h - 5 * mm, f"Q{i+1}.")

        mu.embed_image(c, img_path,
                       box_x + 1 * mm, box_y + 11 * mm,
                       col_w - 2 * mm, row_h - 17 * mm)

        # Answer filled in red
        c.setFont("Helvetica-BoldOblique", 8)
        c.setFillColor(colors.Color(0.7, 0, 0))
        c.drawString(box_x + 10 * mm, box_y + 6 * mm, q['name'])
        c.setFillColor(colors.black)

        c.setStrokeColor(colors.Color(0.85, 0.85, 0.85))
        c.setLineWidth(0.3)
        c.line(box_x, box_y, box_x + col_w, box_y)

    mu.draw_footer(c, "ANSWER KEY")
    c.save()
    print(f"Saved: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    seed = 42
    for arg in sys.argv[1:]:
        if arg.startswith('--seed='):
            seed = int(arg.split('=')[1])

    rng = random.Random(seed)

    # Pick 15 chords ensuring all 4 types are represented
    by_type = {'major': [], 'minor': [], 'dim': [], 'aug': []}
    for c in CHORDS:
        by_type[c['type']].append(c)

    # Guarantee at least 3 of each type, then fill to 15
    selected = []
    for t in ('major', 'minor', 'dim', 'aug'):
        selected += rng.sample(by_type[t], min(3, len(by_type[t])))
    remaining = [c for c in CHORDS if c not in selected]
    rng.shuffle(remaining)
    selected += remaining[:15 - len(selected)]
    rng.shuffle(selected)
    questions = selected[:15]

    print(f"Selected {len(questions)} chords (seed={seed}):")
    for i, q in enumerate(questions, 1):
        print(f"  Q{i:2d}: {q['name']}")

    tmpdir = tempfile.mkdtemp(prefix='chords_')
    try:
        print("\nRendering staves...")
        img_pairs = []   # (blank_png, answer_png) for write worksheet
        id_imgs   = []   # identify stave PNGs

        for i, q in enumerate(questions, 1):
            blank_png, answer_png = _render_chord_pair(q, i, tmpdir)
            id_png = _render_identify_stave(q, i, tmpdir)
            img_pairs.append((blank_png, answer_png))
            id_imgs.append(id_png)
            print(f"  {i:2d}/{len(questions)}  {q['name']}", end='\r')
        print()

        print("Assembling PDFs...")
        build_write_pdf(questions, img_pairs, WRITE_PDF)
        build_identify_pdf(questions, id_imgs, IDENTIFY_PDF)

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print("\nDone!")
    subprocess.run(['open', WRITE_PDF])
    subprocess.run(['open', IDENTIFY_PDF])

if __name__ == '__main__':
    main()
