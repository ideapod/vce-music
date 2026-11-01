#!/usr/bin/env python3
"""
Year 11 Theory revision sheets (one per key) with matching answer keys.

Reproduces the teacher's Theory Sheets #1-3 (C, G, F major) without answers,
and extends the same format to D major and Bb major.

Usage:
    python3 generate_theory_sheets.py            # all five keys
    python3 generate_theory_sheets.py --key=D    # one key (C, G, F, D or Bb)
"""

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import A4

OUTPUT_DIR = "theory_sheets"

# ---------------------------------------------------------------------------
# Music theory
# ---------------------------------------------------------------------------

LETTERS = 'CDEFGAB'
NATURAL_SEMIS = [0, 2, 4, 5, 7, 9, 11]
ACC_TEXT = {-2: 'bb', -1: 'b', 0: '', 1: '#', 2: '##'}
ACC_ABC = {-2: '__', -1: '_', 0: '=', 1: '^', 2: '^^'}

KEY_ACCIDENTALS = {
    'C': {}, 'G': {'F': 1}, 'D': {'F': 1, 'C': 1},
    'F': {'B': -1}, 'Bb': {'B': -1, 'E': -1},
}
RELATIVE_MINOR = {'C': 'A', 'G': 'E', 'D': 'B', 'F': 'D', 'Bb': 'G'}

MAJOR = [(1, 0), (2, 2), (3, 4), (4, 5), (5, 7), (6, 9), (7, 11), (8, 12)]
MAJOR_PENT = [(1, 0), (2, 2), (3, 4), (5, 7), (6, 9), (8, 12)]
NAT_MINOR = [(1, 0), (2, 2), (3, 3), (4, 5), (5, 7), (6, 8), (7, 10), (8, 12)]
MINOR_PENT = [(1, 0), (3, 3), (4, 5), (5, 7), (7, 10), (8, 12)]

INTERVALS = [
    ("Major 2nd", 2, 2), ("min 2nd", 2, 1), ("Maj 3rd", 3, 4),
    ("min 3rd", 3, 3), ("Perfect 4th", 4, 5), ("Augmented 4th", 4, 6),
    ("Perfect 5th", 5, 7), ("Dim 5th", 5, 6), ("Maj 6th", 6, 9),
    ("min 6th", 6, 8), ("Maj 7th", 7, 11), ("min 7th", 7, 10),
]

TRIADS = [
    ("major", "(1, 3, 5)", [(3, 4), (5, 7)]),
    ("augmented", "(1, 3, aug 5)", [(3, 4), (5, 8)]),
    ("minor", "(1, min 3, 5)", [(3, 3), (5, 7)]),
    ("diminished", "(1, min 3, dim 5)", [(3, 3), (5, 6)]),
]

PROGRESSION_SHORT = ["Major", "minor", "minor", "Major", "Major", "minor", "dim"]


def note(name, octave):
    return (LETTERS.index(name[0]), {'': 0, '#': 1, 'b': -1}[name[1:]], octave)


def transpose(n, number, semis):
    li, acc, octave = n
    tli = li + number - 1
    t_oct = octave + tli // 7
    tli %= 7
    target = 12 * octave + NATURAL_SEMIS[li] + acc + semis
    return (tli, target - (12 * t_oct + NATURAL_SEMIS[tli]), t_oct)


def spell(n):
    return LETTERS[n[0]] + ACC_TEXT[n[1]]


def abc_pitch(n, key):
    li, acc, octave = n
    letter = LETTERS[li]
    prefix = '' if acc == KEY_ACCIDENTALS[key].get(letter, 0) else ACC_ABC[acc]
    if octave >= 5:
        return prefix + letter.lower() + "'" * (octave - 5)
    return prefix + letter + "," * (4 - octave)


def scale_notes(tonic, degrees):
    return [transpose(tonic, num, semis) for num, semis in degrees]


def diatonic_triad(tonic, degree):
    two_oct = scale_notes(tonic, MAJOR[:7]) + scale_notes(
        transpose(tonic, 8, 12), MAJOR[:7])
    i = degree - 1
    return [two_oct[i], two_oct[i + 2], two_oct[i + 4]]


def chord_name(root, quality):
    return f"{spell(root)} {quality}"


# ---------------------------------------------------------------------------
# Per-key configuration (clef + starting octave for each stave)
# ---------------------------------------------------------------------------

@dataclass
class KeySheet:
    key: str
    sheet_no: int
    interval_tonic: tuple
    chord_stave: tuple            # (clef, tonic note)
    major_desc: tuple             # (clef, bottom tonic) – written top-down
    major_pent: tuple             # (clef, start tonic)
    nat_minor: tuple              # (clef, start tonic) – relative minor
    minor_pent: tuple             # (clef, start tonic) – relative minor
    progression_tonic: tuple
    keysig_mode: str              # 'name' or 'draw'
    keysig_keys: list
    theory: str                   # 'A', 'B' or 'C' (back-of-sheet rotation)


SHEETS = {
    'C': KeySheet('C', 1, note('C', 3), ('treble', note('C', 4)),
                  ('treble', note('C', 4)), ('treble', note('C', 4)),
                  ('bass', note('A', 2)), ('treble', note('A', 4)),
                  note('C', 4), 'name', ['C', 'G', 'D', 'F', 'Bb'], 'A'),
    'G': KeySheet('G', 2, note('G', 2), ('bass', note('G', 2)),
                  ('bass', note('G', 2)), ('treble', note('G', 4)),
                  ('bass', note('E', 2)), ('treble', note('E', 4)),
                  note('G', 4), 'draw', ['C', 'F', 'Bb', 'G', 'D'], 'B'),
    'F': KeySheet('F', 3, note('F', 2), ('bass', note('F', 2)),
                  ('bass', note('F', 2)), ('treble', note('F', 4)),
                  ('treble', note('D', 4)), ('treble', note('D', 4)),
                  note('F', 4), 'draw', ['C', 'F', 'Bb', 'G', 'D'], 'C'),
    'D': KeySheet('D', 4, note('D', 3), ('treble', note('D', 4)),
                  ('treble', note('D', 4)), ('treble', note('D', 4)),
                  ('bass', note('B', 2)), ('bass', note('B', 2)),
                  note('D', 4), 'name', ['C', 'F', 'D', 'Bb', 'G'], 'A'),
    'Bb': KeySheet('Bb', 5, note('Bb', 2), ('bass', note('Bb', 2)),
                   ('bass', note('Bb', 2)), ('bass', note('Bb', 2)),
                   ('bass', note('G', 2)), ('treble', note('G', 4)),
                   note('Bb', 3), 'draw', ['C', 'D', 'G', 'Bb', 'F'], 'B'),
}

# ---------------------------------------------------------------------------
# Stave rendering: ABC → PNG, then locate staff lines and barlines
# ---------------------------------------------------------------------------

RES = 300


@dataclass
class Stave:
    path: str
    w_pt: float
    h_pt: float
    bars: list = field(default_factory=list)   # barline x positions (pt, from left)


def render_stave(abc_body, out_png, width_cm, scale=0.8):
    page_w = width_cm + 1.0
    header = (
        f"%%pagewidth {page_w}cm\n%%pageheight 8cm\n%%scale {scale}\n"
        "%%leftmargin 0.5cm\n%%rightmargin 0.5cm\n"
        "%%topmargin 1.5cm\n%%botmargin 0.5cm\n"
        "%%stretchlast 1\n%%staffnonote 2\n%%cancelkey 0\n%%writefields T 0\n"
    )
    tmpdir = tempfile.mkdtemp()
    abc_path = os.path.join(tmpdir, 's.abc')
    ps_path = os.path.join(tmpdir, 's.ps')
    with open(abc_path, 'w') as f:
        f.write(header + abc_body)
    # abcm2ps exits 1 on harmless warnings, so check for output instead.
    subprocess.run(['abcm2ps', abc_path, '-O', ps_path, '-q'], capture_output=True)
    if not os.path.exists(ps_path):
        raise RuntimeError(f"abcm2ps produced no output:\n{abc_body}")
    subprocess.run(['gs', '-dNOPAUSE', '-dBATCH', '-dQUIET', '-sDEVICE=pnggray',
                    f'-r{RES}', f'-sOutputFile={tmpdir}/p%d.png', ps_path],
                   check=True, capture_output=True)
    pages = sorted(p for p in os.listdir(tmpdir) if p.endswith('.png'))
    imgs = [Image.open(os.path.join(tmpdir, p)).convert('L') for p in pages]
    img = max(imgs, key=lambda im: sum(im.histogram()[:128]))
    return _crop_stave(img, out_png)


def _crop_stave(img, out_png):
    w, h = img.size
    px = img.load()
    dark = lambda x, y: px[x, y] < 128

    rows = [y for y in range(h) if sum(1 for x in range(0, w, 2) if dark(x, y)) > w * 0.25]
    lines = []
    for y in rows:
        if lines and y - lines[-1][-1] <= 2:
            lines[-1].append(y)
        else:
            lines.append([y])
    centres = [sum(g) / len(g) for g in lines]
    if len(centres) != 5:
        raise RuntimeError(f"Expected 5 staff lines, found {len(centres)}")
    y0, y4 = int(lines[0][0]), int(lines[-1][-1])
    sp = (centres[4] - centres[0]) / 4

    top_row = lines[0][len(lines[0]) // 2]
    xs = [x for x in range(w) if dark(x, top_row)]
    left, right = xs[0], xs[-1]

    clef_skip = int(1.3 / 2.54 * RES)
    span = y4 - y0 + 1
    cols = [x for x in range(left + clef_skip, right + 1)
            if sum(1 for y in range(y0, y4 + 1) if dark(x, y)) >= span * 0.95]
    groups = []
    for x in cols:
        if groups and x - groups[-1][-1] <= 8:
            groups[-1].append(x)
        else:
            groups.append([x])
    bar_px = [g[-1] if g[-1] >= right - 2 else (g[0] + g[-1]) / 2 for g in groups]

    pad = 2
    top = int(centres[0] - 3.2 * sp)
    bottom = int(centres[4] + 3.0 * sp)
    out = Image.new('L', (right - left + 2 * pad, bottom - top), 255)
    out.paste(img.crop((left - pad, max(top, 0), right + pad, min(bottom, h))),
              (0, max(0, -top)))
    out.save(out_png)
    to_pt = 72.0 / RES
    return Stave(out_png, out.width * to_pt, out.height * to_pt,
                 [(b - left + pad) * to_pt for b in bar_px])


def abc_tune(key, clef, body, unit='1/1'):
    return f"X:1\nM:none\nL:{unit}\nK:{key} clef={clef}\n{body}\n"


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4
MX = 15 * mm
CONTENT_W = PAGE_W - 2 * MX
TOP = PAGE_H - 14 * mm
BOTTOM = 16 * mm
ANSWER_COLOUR = colors.Color(0.1, 0.2, 0.65)
FONT, BOLD = "Times-Roman", "Times-Bold"


class Flow:
    """Places fixed-height blocks top-to-bottom, starting a new page when needed."""

    def __init__(self, c, title_lines, footer):
        self.c = c
        self.footer = footer
        self.title_lines = title_lines
        self.page = 1
        self.pending = None
        self.y = self._header(first=True)

    def _header(self, first):
        c = self.c
        if first:
            c.setFont(FONT, 20)
            y = TOP - 4
            for line in self.title_lines:
                c.drawCentredString(PAGE_W / 2, y, line)
                y -= 24
            c.setFont(FONT, 13)
            c.drawString(PAGE_W - MX - 200, y + 2, "Name: ______________________")
            return y - 16
        c.setFont(FONT, 10)
        c.setFillColor(colors.grey)
        c.drawRightString(PAGE_W - MX, TOP, f"{self.title_lines[-1]} – page {self.page}")
        c.setFillColor(colors.black)
        return TOP - 18

    def _footer(self):
        self.c.setFont(FONT, 8)
        self.c.setFillColor(colors.grey)
        self.c.drawCentredString(PAGE_W / 2, 9 * mm, self.footer)
        self.c.setFillColor(colors.black)

    def hold(self, height, draw):
        """Queue a heading so it is placed on the same page as the next block."""
        self.pending = (height, draw)

    def add(self, height, draw):
        if self.pending:
            (head_h, head_draw), self.pending = self.pending, None

            def combined(c, y, body=draw):
                head_draw(c, y)
                body(c, y - head_h)
            height, draw = head_h + height, combined
        if self.y - height < BOTTOM:
            self._footer()
            self.c.showPage()
            self.page += 1
            self.y = self._header(first=False)
        draw(self.c, self.y)
        self.y -= height

    def finish(self):
        self._footer()
        self.c.save()


def rich_line(c, x, y, parts, size=12):
    """Draw [(text, bold), ...] on one line."""
    for text, bold in parts:
        font = BOLD if bold else FONT
        c.setFont(font, size)
        c.drawString(x, y, text)
        x += c.stringWidth(text, font, size)


def heading_block(flow, parts, sub=None):
    h = 18 + (15 if sub else 0)

    def draw(c, y):
        rich_line(c, MX, y - 13, parts)
        if sub:
            c.setFont(FONT, 11)
            c.drawString(MX + 12, y - 28, sub)
    return h, draw


LABEL_LINE = 13


def stave_block(stave, x, labels, colour=colors.black, label_size=11):
    """(height, draw) for a stave image with labels (may contain newlines) centred under each bar."""
    n_lines = max(label.count("\n") + 1 for label in labels)

    def draw(c, y):
        c.drawImage(stave.path, x, y - stave.h_pt, stave.w_pt, stave.h_pt)
        bars = stave.bars
        widths = [b - a for a, b in zip(bars, bars[1:])]
        avg = sum(widths) / len(widths) if widths else stave.w_pt / 4
        centres = [bars[0] - avg / 2] + [(a + b) / 2 for a, b in zip(bars, bars[1:])]
        c.setFillColor(colour)
        for centre, label in zip(centres, labels):
            lines = label.split("\n")
            size = label_size
            while max(c.stringWidth(t, FONT, size) for t in lines) > avg - 4 and size > 7:
                size -= 0.5
            c.setFont(FONT, size)
            for j, text in enumerate(lines):
                c.drawCentredString(x + centre, y - stave.h_pt - 3 - LABEL_LINE * j, text)
        c.setFillColor(colors.black)
    return stave.h_pt + 6 + LABEL_LINE * n_lines, draw


# ---------------------------------------------------------------------------
# Sheet content
# ---------------------------------------------------------------------------

class SheetBuilder:
    def __init__(self, ks, answers, tmpdir):
        self.ks = ks
        self.key = ks.key
        self.answers = answers
        self.tmp = tmpdir
        self.n = 0
        self.marks = 0
        self.rel = RELATIVE_MINOR[self.key]
        self.label_colour = ANSWER_COLOUR if answers else colors.black

    def _png(self, tag):
        self.n += 1
        return os.path.join(self.tmp, f"{tag}_{self.n}.png")

    def build(self, path):
        ks = self.ks
        c = rl_canvas.Canvas(path, pagesize=A4)
        suffix = " – ANSWERS" if self.answers else ""
        flow = Flow(c, ["Year 11 Theory", f"Sheet #{ks.sheet_no} ({self.key} Major){suffix}"],
                    f"Year 11 Theory – Sheet #{ks.sheet_no} ({self.key} Major)")
        self.section = 0
        self.intervals(flow)
        self.scales(flow)
        self.chords(flow)
        self.key_signatures(flow)
        {'A': self.theory_a, 'B': self.theory_b, 'C': self.theory_c}[ks.theory](flow)
        self.total(flow)
        flow.finish()

    def next_section(self):
        self.section += 1
        return f"{self.section}) "

    # -- Intervals ----------------------------------------------------------

    def intervals(self, flow):
        key, tonic = self.key, self.ks.interval_tonic
        self.marks += 12
        flow.hold(*heading_block(flow, [(self.next_section(), False), ("Write", True),
                 (" the following intervals ", False), ("above", True),
                 (" the given note as indicated.  (12 marks)", False)]))
        for row in (INTERVALS[:6], INTERVALS[6:]):
            bars = []
            for _, num, semis in row:
                lo = abc_pitch(tonic, key)
                if self.answers:
                    bars.append(f"[{lo}{abc_pitch(transpose(tonic, num, semis), key)}]")
                else:
                    bars.append(lo)
            stave = render_stave(abc_tune(key, 'bass', " | ".join(bars) + " |]"),
                                 self._png('int'), 18)
            labels = [name for name, _, _ in row]
            if self.answers:
                labels = [f"{name}\n{spell(transpose(tonic, num, semis))}"
                          for name, num, semis in row]
            flow.add(*stave_block(stave, MX, labels, self.label_colour))

    # -- Scales -------------------------------------------------------------

    def _scale_stave(self, clef, start, degrees, length, descending, show_key):
        notes = scale_notes(start, degrees)
        if descending:
            notes = notes[::-1]
        key = show_key if self.answers else 'C'
        parts = []
        for i, n in enumerate(notes):
            if self.answers or i == 0:
                parts.append(f"{abc_pitch(n, key)}{length}")
            else:
                parts.append(f"x{length}")
        return render_stave(abc_tune(key, clef, " ".join(parts) + " |]", unit='1/8'),
                            self._png('scale'), 8.6)

    def scales(self, flow):
        ks, key, rel = self.ks, self.key, self.rel
        self.marks += 8
        flow.hold(*heading_block(
            flow, [(self.next_section(), False), ("Write", True),
                   (" the following scale forms beginning on the given tonic note, using the", False)],
            sub="given rhythmic value. Remember correct stem direction!  (8 marks)"))
        specs = [
            (ks.major_desc, MAJOR, '4', True, key, f"{key} Major descending"),
            (ks.major_pent, MAJOR_PENT, '2', False, key,
             f"{key} Major Pentatonic ascending (1, 2, 3, 5, 6, 8)"),
            (ks.nat_minor, NAT_MINOR, '1', False, key,
             f"{rel} natural minor ascending"),
            (ks.minor_pent, MINOR_PENT, '2', False, key,
             f"{rel} minor pentatonic ascending (1, m3, 4, 5, m7, 8)"),
        ]
        staves = [(self._scale_stave(clef, start, deg, length, desc, show), label)
                  for (clef, start), deg, length, desc, show, label in specs]
        half = (CONTENT_W - 8 * mm) / 2
        for pair in (staves[:2], staves[2:]):
            h = max(s.h_pt for s, _ in pair) + 20

            def draw(c, y, pair=pair):
                for i, (s, label) in enumerate(pair):
                    x = MX + i * (half + 8 * mm)
                    c.drawImage(s.path, x, y - s.h_pt, s.w_pt, s.h_pt)
                    c.setFont(FONT, 11)
                    c.drawString(x + 4, y - s.h_pt - 3, label)
            flow.add(h, draw)

    # -- Individual chords ---------------------------------------------------

    def chords(self, flow):
        key = self.key
        clef, root = self.ks.chord_stave
        self.marks += 4
        flow.hold(*heading_block(flow, [(self.next_section(), False), ("Write", True),
                 (" the following chords in root position.  (4 marks)", False)]))
        bars, labels = [], []
        for quality, formula, tones in TRIADS:
            chord = [root] + [transpose(root, n, s) for n, s in tones]
            if self.answers:
                bars.append("[" + "".join(abc_pitch(n, key) for n in chord) + "]")
                labels.append(f"{key} {quality}\n" + " ".join(spell(n) for n in chord))
            else:
                bars.append("x")
                labels.append(f"{key} {quality}\n{formula}")
        stave = render_stave(abc_tune(key, clef, " | ".join(bars) + " |]"),
                             self._png('chord'), 18)
        flow.add(*stave_block(stave, MX, labels, self.label_colour))

    # -- Key signatures -------------------------------------------------------

    def key_signatures(self, flow):
        keys = self.ks.keysig_keys
        if self.ks.keysig_mode == 'name':
            marks = 2 * (len(keys) - 1)
            parts = [(self.next_section(), False), ("Name", True),
                     (" the following key signatures and their ", False),
                     ("relative minors", True), (f".  ({marks} marks)", False)]
            body = " | ".join(("" if i == 0 else f"[K:{k}] ") + "x"
                              for i, k in enumerate(keys)) + " |]"
            clef = 'bass'
            labels = []
            for i, k in enumerate(keys):
                pair = f"{k} maj / {RELATIVE_MINOR[k]} min"
                if i == 0:
                    labels.append(f"1. eg: {pair}")
                else:
                    labels.append(f"{i + 1}. {pair if self.answers else '_' * 16}")
        else:
            marks = 2 * len(keys)
            parts = [(self.next_section(), False), ("Draw", True),
                     (" the following key signatures and ", False),
                     ("name their relative minors", True), (f".  ({marks} marks)", False)]
            if self.answers:
                body = " | ".join(("" if i == 0 else f"[K:{k}] ") + "x"
                                  for i, k in enumerate(keys)) + " |]"
            else:
                body = " | ".join("x" for _ in keys) + " |]"
            clef = 'treble'
            labels = [f"{i + 1}. {k} Maj / "
                      + (f"{RELATIVE_MINOR[k]} min" if self.answers else "_" * 9)
                      for i, k in enumerate(keys)]
        self.marks += marks
        flow.hold(*heading_block(flow, parts))
        stave = render_stave(abc_tune(keys[0], clef, body), self._png('ks'), 18)
        flow.add(*stave_block(stave, MX, labels, self.label_colour))

    # -- Back-of-sheet theory sections (rotated between keys) ---------------

    def progression_stave(self, flow, parts, marks):
        key, tonic = self.key, self.ks.progression_tonic
        self.marks += marks
        flow.hold(*heading_block(flow, parts))
        bars, labels = [], []
        for deg in range(1, 8):
            triad = diatonic_triad(tonic, deg)
            if self.answers:
                bars.append("[" + "".join(abc_pitch(n, key) for n in triad) + "]")
                labels.append(f"{deg}. {chord_name(triad[0], PROGRESSION_SHORT[deg - 1])}")
            else:
                bars.append("x")
                labels.append(f"{deg}. ____________")
        k = key if self.answers else 'C'
        stave = render_stave(abc_tune(k, 'treble', " | ".join(bars) + " |]"),
                             self._png('prog'), 18)
        flow.add(*stave_block(stave, MX, labels, self.label_colour))

    def quality_blanks(self, flow):
        self.marks += 7
        flow.hold(*heading_block(flow, [(self.next_section(), False), ("Write", True),
                 (" the ", False), ("Major Chord Progression", True),
                 (" (the chord quality on each scale degree).  (7 marks)", False)]))

        def draw(c, y):
            w = CONTENT_W / 7
            for i in range(7):
                x = MX + i * w
                c.setFont(FONT, 11)
                c.drawString(x, y - 22, f"{i + 1}.")
                c.line(x + 12, y - 24, x + w - 6, y - 24)
                if self.answers:
                    c.setFillColor(ANSWER_COLOUR)
                    c.drawCentredString(x + 12 + (w - 18) / 2, y - 21, PROGRESSION_SHORT[i])
                    c.setFillColor(colors.black)
        flow.add(34, draw)

    def written_lines(self, flow, items, marks, intro_parts, line_count=1, label_w=0):
        """Numbered prompts each followed by writing line(s); answers filled in when needed."""
        self.marks += marks
        head_h, head_draw = heading_block(flow, intro_parts)
        for i, (prompt, answer) in enumerate(items):
            text_x = MX + 14 + label_w
            ans_lines = simpleSplit(answer, FONT, 11, PAGE_W - MX - text_x - 4) if self.answers else []
            n = max(line_count, len(ans_lines))
            h = 8 + 20 * n

            def draw(c, y, prompt=prompt, ans_lines=ans_lines, n=n):
                c.setFont(FONT, 12)
                c.drawString(MX + 14, y - 16, prompt)
                for j in range(n):
                    ly = y - 18 - 20 * j
                    c.setStrokeColor(colors.Color(0.6, 0.6, 0.6))
                    c.line(text_x, ly, PAGE_W - MX, ly)
                    c.setStrokeColor(colors.black)
                    if j < len(ans_lines):
                        c.setFont(FONT, 11)
                        c.setFillColor(ANSWER_COLOUR)
                        c.drawString(text_x + 2, ly + 3, ans_lines[j])
                        c.setFillColor(colors.black)
            if i == 0:
                def draw_with_heading(c, y, draw=draw):
                    head_draw(c, y)
                    draw(c, y - head_h)
                flow.add(head_h + h, draw_with_heading)
            else:
                flow.add(h, draw)
        flow.add(8, lambda c, y: None)

    def theory_a(self, flow):
        key = self.key
        self.quality_blanks(flow)
        self.progression_stave(flow, [(self.next_section(), False), ("Name", True),
                               (" and ", False), ("write", True),
                               (f" the chords for a {key} Major chord progression. "
                                "Use a key signature or accidentals.  (14 marks)", False)], 14)
        tonic = note(key, 4)
        I, IV, V = (diatonic_triad(tonic, d)[0] for d in (1, 4, 5))
        self.written_lines(flow, [("", f"V – I (dominant to tonic). In {key} major: "
                                   f"{spell(V)} major to {spell(I)} major.")], 2,
                           [(self.next_section(), False), ("Name the 2 chords used for a ", False),
                            ("Perfect Cadence", True), ("  (2 marks)", False)])
        self.written_lines(flow, [("", f"IV – I (subdominant to tonic). In {key} major: "
                                   f"{spell(IV)} major to {spell(I)} major.")], 2,
                           [(self.next_section(), False), ("Name the 2 chords used for a ", False),
                            ("Plagal Cadence", True), ("  (2 marks)", False)])
        devices = [
            ("a)", "Repetition – repeating a musical idea; builds familiarity and unity."),
            ("b)", "Contrast – introducing a new or different musical idea to break monotony."),
            ("c)", "Variation – taking an existing idea and changing parts of it, "
                   "so it is still recognisable."),
            ("d)", "Transition – material that connects one section of the music to another."),
        ]
        self.written_lines(flow, devices, 4,
                           [(self.next_section(), False), ("List the ", False),
                            ("4 compositional devices", True), (" and their ", False),
                            ("definitions", True), (".  (4 marks)", False)],
                           line_count=2, label_w=12)

    def theory_b(self, flow):
        key = self.key
        self.progression_stave(flow, [(self.next_section(), False), ("Write", True),
                               (f" and name the chords for a {key} Major chord progression. "
                                "Use a key signature or accidentals.  (14 marks)", False)], 14)
        elements = [
            ("1. Duration:", "How long sounds and silences last – includes rhythm, metre and tempo."),
            ("2. Dynamics:", "How loud or soft the music is, and how the volume changes."),
            ("3. Texture:", "How many layers of sound are heard at once and how they interact."),
            ("4. Tone Colour:", "The unique quality of a sound that makes one instrument or "
                                "voice sound different from another."),
            ("5. Structure:", "How the music is organised – macro (overall form) and "
                              "micro (phrases, motifs)."),
            ("6. Articulation:", "How notes are played or sung (e.g. legato, staccato, accents)."),
            ("7. Pitch:", "How high or low a sound is – includes melody, harmony and tonality."),
        ]
        self.written_lines(flow, elements, 7,
                           [(self.next_section(), False),
                            ("Write a definition for each of the following ", False),
                            ("Musical Elements", True),
                            (" used in Listening Analysis.  (7 marks)", False)],
                           label_w=82)

    def theory_c(self, flow):
        key = self.key
        self.progression_stave(flow, [(self.next_section(), False), ("Write", True),
                               (f" the following chords for a {key} Major chord progression. "
                                "Use a key signature or accidentals.  (7 marks)", False)], 7)
        colours = [
            ("a) Bright", "e.g. trumpet, piccolo, flute (high register), glockenspiel"),
            ("b) Aspirate", "e.g. breathy voice, flute (low register), pan pipes"),
            ("c) Mellow", "e.g. cello, French horn, clarinet (low register)"),
            ("d) Dark", "e.g. bass clarinet, tuba, double bass, distorted electric guitar"),
        ]
        self.written_lines(flow, colours, 4,
                           [(self.next_section(), False), ("Listening Analysis.", True),
                            (" List an instrument that would have the following tone colour.  "
                             "(4 marks)", False)],
                           label_w=62)

    def total(self, flow):
        def draw(c, y):
            c.setFont(BOLD, 14)
            c.drawString(MX, y - 24, f"TOTAL:  ______ / {self.marks}")
        flow.add(30, draw)


def generate(key):
    ks = SHEETS[key]
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base = os.path.join(OUTPUT_DIR, f"theory_sheet_{ks.sheet_no}_{key}_major")
    outputs = []
    with tempfile.TemporaryDirectory() as tmp:
        for answers, path in ((False, base + ".pdf"), (True, base + "_ANSWERS.pdf")):
            SheetBuilder(ks, answers, tmp).build(path)
            outputs.append(path)
    return outputs


def main():
    keys = list(SHEETS)
    for arg in sys.argv[1:]:
        if arg.startswith('--key='):
            keys = [arg.split('=', 1)[1]]
    for key in keys:
        if key not in SHEETS:
            sys.exit(f"Unknown key {key!r}; choose from {', '.join(SHEETS)}")
        for path in generate(key):
            print(f"Wrote {path}")


if __name__ == '__main__':
    main()
