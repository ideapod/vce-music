# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Printable VCE Music Unit 1 worksheet generators for a Year 11 student. The source-of-truth for exam scope is `Unit 1- Exam Checklist.docx`.

## Commands

```bash
# Intervals worksheet (20 questions, A4, 2 cols × 10 rows)
python3 generate_intervals_worksheet.py
python3 generate_intervals_worksheet.py --answers        # also writes answer key PDF
python3 generate_intervals_worksheet.py --seed=99        # different random set

# Scales worksheet (all 20 VCE scales, 4 pages: questions then answers)
python3 generate_scales_worksheet.py
python3 generate_scales_worksheet.py --select            # random 10 scales (2 pages)
python3 generate_scales_worksheet.py --select --seed=5

# Chords worksheets (2 PDFs: write + identify, 15 questions each, 2 pages each)
python3 generate_chords_worksheet.py
python3 generate_chords_worksheet.py --seed=99
```

## Dependencies

| Package | Purpose | Install |
|---------|---------|---------|
| `reportlab` | PDF assembly | `pip3 install reportlab` |
| `Pillow` | Image cropping & stave blanking | `pip3 install Pillow` |
| `abcm2ps` | ABC notation → PostScript | `brew install abcm2ps` |
| `ghostscript` (`gs`) | PostScript → PNG | `brew install ghostscript` |

## Architecture

### Shared module: `music_utils.py`

- `render_abc_to_png(abc_body, output_png, ...)` — writes a temp `.abc` file, runs `abcm2ps`, then Ghostscript. **abcm2ps always emits a blank page 1 then music on page 2**, so Ghostscript is called with `-dFirstPage=2 -dLastPage=2`. abcm2ps also returns exit code 1 for non-fatal warnings (e.g. "staffwidth too big") while still producing valid output, so the function checks for the output file rather than the exit code.
- `make_blank_stave(answer_img_path, output_path)` — derives a blank stave from an answer stave PNG using PIL. Identifies the 5 staff lines as rows where >35% of pixels are dark (horizontal runs), protects the leftmost 22% of the image as the treble clef + key signature region, then whites out all non-staff-line pixels to the right of that boundary.
- `crop_image(img)` — trims whitespace from a PIL Image.
- `draw_page_header`, `embed_image`, `draw_footer` — ReportLab page layout helpers.

### Intervals script: `generate_intervals_worksheet.py`

Question generation computes the upper note from (lower note, semitone count, diatonic step count). If the chromatic distance between the computed diatonic position and the target pitch is ±1 semitone, it applies a sharp or flat; if it's ±2 (double accidental), the question is skipped. Questions are drawn from a pool ensuring all 12 VCE interval types appear.

### Scales script: `generate_scales_worksheet.py`

Scale data is defined explicitly (ABC note strings + K: key field) for all 20 scales. The answer stave is rendered first, then `make_blank_stave()` strips the notes to produce the question stave — this guarantees blank and answer staves are identical in size. The PDF is structured as all question pages followed by all answer pages.

### Chords script: `generate_chords_worksheet.py`

20 chords defined (5 major, 5 minor, 5 diminished, 5 augmented) covering all VCE keys up to 2 sharps/flats. Selects a random 15 ensuring ≥3 of each type. Produces two PDFs:

- **`chords_write_worksheet.pdf`**: Text prompt ("Write a D augmented chord") + blank stave, then answer page. Blank stave is derived by rendering the chord at 22cm width so the gap-detection in `make_blank_stave()` can reliably find the clef boundary (at 12cm the chord lands too close to the clef).
- **`chords_identify_worksheet.pdf`**: Chord shown on stave with appropriate key signature, student writes name on line below, then answer page. Layout is 3 cols × 5 rows per page.

## ABC Notation Conventions

- Uppercase letter = octave 4 (`C`=C4 … `B`=B4); lowercase = octave 5 (`c`=C5)
- Comma suffix = octave down (`B,`=B3); apostrophe suffix = octave up (`c'`=C6)
- `^` prefix = sharp, `_` prefix = flat, `=` prefix = natural
- Key signature set via `K:` field (e.g. `K:G`, `K:Bb`, `K:Emin`) — the key sig handles accidentals implicitly so note strings use plain diatonic letters

## VCE Exam Scope (from Checklist)

- **Intervals**: Identify/write major, minor, perfect, augmented, diminished. Aurally recognise major, minor & perfect.
- **Scales**: Major, major pentatonic, natural minor, minor pentatonic — up to 2 sharps and 2 flats (keys: C, G, D, F, Bb major and relative minors A, E, B, D, G minor).
- **Key signatures**: Up to 2 sharps/flats.
- **Chords**: Write/recognise major, minor, diminished, augmented. Major chord progression: I=Maj, ii=min, iii=min, IV=Maj, V=Maj, vi=min, vii°=dim.
- **Melodic/harmonic/rhythmic transcription** also examined (no worksheet yet).
