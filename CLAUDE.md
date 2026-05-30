# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This repo contains tools for generating printable VCE Music Unit 1 study worksheets for a Year 11 student. The source-of-truth for exam content is `Unit 1- Exam Checklist.docx`.

## Generating Worksheets

```bash
# Generate worksheet (blank answer lines)
python3 generate_intervals_worksheet.py

# Generate worksheet + answer key
python3 generate_intervals_worksheet.py --answers

# Generate a different random question set
python3 generate_intervals_worksheet.py --seed=99 --answers
```

Outputs: `intervals_worksheet.pdf` and (with `--answers`) `intervals_worksheet_ANSWERS.pdf`.

## Dependencies

- `reportlab` — PDF assembly (`pip3 install reportlab`)
- `PIL` (Pillow) — image cropping (`pip3 install Pillow`)
- `abcm2ps` — renders ABC music notation to PostScript (`brew install abcm2ps`)
- `ghostscript` (`gs`) — converts PostScript to PNG (`brew install ghostscript`)

## How the Script Works

1. **Question generation** — builds 20 interval pairs using `build_questions()`. Each question is a lower note + upper note within the comfortable treble range (C4–E5 for the lower note). Covers all VCE interval types: Major/Minor 2nd–7th, Perfect 4th/5th/Octave, Augmented 4th, Diminished 5th.

2. **ABC notation rendering** — each question is written as an ABC notation file and passed to `abcm2ps`, which outputs PostScript. Ghostscript converts it to a PNG. **Important:** `abcm2ps` always outputs 2 pages (blank title page first, music on page 2), so the renderer explicitly requests `-dFirstPage=2 -dLastPage=2` from Ghostscript.

3. **PDF assembly** — ReportLab composes the final A4 PDF in a 2-column × 10-row grid. Each cell contains the cropped stave image (via PIL auto-crop), a question number label, and an "Interval:" answer line drawn below.

## ABC Notation Note Encoding

In ABC notation as used here:
- Uppercase = octave 4 (C = C4, A = A4, etc.)
- Lowercase = octave 5 (c = C5, a = A5, etc.)
- `^` prefix = sharp, `_` prefix = flat
- Note duration `2` = half note (used for both notes in each question)

## VCE Exam Scope (from Checklist)

- **Intervals**: Identify and/or write major, minor, perfect, augmented, and diminished intervals. Aurally recognise major, minor & perfect intervals.
- **Scales**: Major, major pentatonic, natural minor, minor pentatonic — up to 2 sharps and 2 flats.
- **Key signatures**: Up to 2 sharps and 2 flats (C, G, D, F, Bb major and their relative minors).
- **Chords**: Write and recognise major, minor, diminished, augmented. Major chord progression: I=Maj, ii=min, iii=min, IV=Maj, V=Maj, vi=min, vii°=dim.
