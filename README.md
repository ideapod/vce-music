# VCE Music Unit 1 — Worksheet Generator

Printable practice worksheets for VCE Music Unit 1 theory, generated from Python scripts. Currently covers intervals and scales.

## Requirements

```bash
pip3 install reportlab Pillow
brew install abcm2ps ghostscript
```

## Worksheets

### Intervals

20 questions per page. Each question shows two notes on a treble clef stave; the student identifies the interval and writes it on the line below.

Covers all VCE interval types: Major/Minor 2nd–7th, Perfect 4th/5th/Octave, Augmented 4th, Diminished 5th.

```bash
python3 generate_intervals_worksheet.py              # intervals_worksheet.pdf
python3 generate_intervals_worksheet.py --answers    # + intervals_worksheet_ANSWERS.pdf
python3 generate_intervals_worksheet.py --seed=99    # different random set
```

### Scales

All 20 scales from the VCE Unit 1 exam scope across 4 pages: 2 question pages (blank staves with key signature and scale name prompt) followed by 2 answer pages.

Covers: major, natural minor, major pentatonic, minor pentatonic — in keys up to 2 sharps and 2 flats (C, G, D, F, Bb and relative minors).

```bash
python3 generate_scales_worksheet.py                 # scales_worksheet.pdf (all 20, 4 pages)
python3 generate_scales_worksheet.py --select        # random 10 scales (2 pages)
python3 generate_scales_worksheet.py --select --seed=5
```

## How It Works

Music notation is written as [ABC notation](https://abcnotation.com/), rendered to PostScript by `abcm2ps`, converted to PNG by Ghostscript, then assembled into a PDF by ReportLab. Shared rendering utilities live in `music_utils.py`.

For scales, blank staves are derived from the answer stave image: the treble clef and key signature are preserved (left 22% of the image) and everything else except the five staff lines is whited out with PIL.

## VCE Exam Scope

From `Unit 1- Exam Checklist.docx`:

| Topic | What's tested |
|-------|--------------|
| Intervals | Identify and write major, minor, perfect, augmented, diminished intervals |
| Scales | Write major, major pentatonic, natural minor, minor pentatonic (up to 2♯/2♭) |
| Key signatures | Up to 2 sharps and 2 flats |
| Chords | Write/recognise major, minor, diminished, augmented; major chord progression |
| Transcription | Melodic (rhythm given), harmonic, rhythmic |
