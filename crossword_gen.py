"""Crossword puzzle generator.

Takes a list of {word, clue} pairs, places them on a grid via greedy
intersection, renders the grid to PNG and produces a clue list.

Usage:
  python3 crossword_gen.py words.json out_image.png out_clues.json
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

GRID_MAX = 21  # max grid dimension


def _try_place(grid: dict, word: str, row: int, col: int, direction: str) -> bool:
    """Returns True if word can be placed at (row,col) in direction without
    conflict. Direction is 'H' or 'V'."""
    dr, dc = (0, 1) if direction == "H" else (1, 0)
    # Cell before start must be empty/edge, cell after end must be empty/edge
    pre = (row - dr, col - dc)
    if pre in grid:
        return False
    post = (row + dr * len(word), col + dc * len(word))
    if post in grid:
        return False
    for i, ch in enumerate(word):
        cell = (row + dr * i, col + dc * i)
        existing = grid.get(cell)
        if existing is None:
            # Adjacent cells perpendicular to placement direction must be clear
            # unless they are the start/end of an intersecting word
            for perp in [(cell[0] + dc, cell[1] + dr), (cell[0] - dc, cell[1] - dr)]:
                if perp in grid:
                    return False
        elif existing != ch:
            return False
    return True


def _commit(grid: dict, word: str, row: int, col: int, direction: str) -> tuple:
    dr, dc = (0, 1) if direction == "H" else (1, 0)
    cells = []
    for i, ch in enumerate(word):
        cell = (row + dr * i, col + dc * i)
        grid[cell] = ch
        cells.append(cell)
    return (word, row, col, direction, cells)


def build_grid(words: list[dict], rng: random.Random) -> tuple[dict, list]:
    """Return (cell_map, placements) where placements is list of
    (word, row, col, direction, [cells])."""
    if not words:
        return {}, []
    sorted_words = sorted(words, key=lambda w: -len(w["word"]))
    grid = {}
    placements = []

    # Place first word horizontally near center
    first = sorted_words[0]
    row, col = 0, 0
    placements.append(_commit(grid, first["word"].upper(), row, col, "H"))

    for entry in sorted_words[1:]:
        word = entry["word"].upper()
        placed = False
        # Try every placement that intersects an existing word at a matching letter
        candidates = []
        for i, ch in enumerate(word):
            for cell, existing in list(grid.items()):
                if existing != ch:
                    continue
                # Try placing word perpendicular to existing word at this cell
                # Need to know direction of existing — find it
                for direction in ("H", "V"):
                    dr, dc = (0, 1) if direction == "H" else (1, 0)
                    r0 = cell[0] - dr * i
                    c0 = cell[1] - dc * i
                    if _try_place(grid, word, r0, c0, direction):
                        candidates.append((r0, c0, direction))
        rng.shuffle(candidates)
        # Pick a candidate roughly central to the existing grid
        if candidates:
            rows = [c[0] for c in grid.keys()]
            cols = [c[1] for c in grid.keys()]
            cx = sum(rows) / len(rows)
            cy = sum(cols) / len(cols)
            candidates.sort(key=lambda x: abs(x[0] - cx) + abs(x[1] - cy))
            r, c, d = candidates[0]
            placements.append(_commit(grid, word, r, c, d))
            placed = True
        if not placed:
            # Skip this word — couldn't fit
            entry["_skipped"] = True

    return grid, placements


def normalize_grid(grid: dict, placements: list) -> tuple[dict, list, int, int]:
    if not grid:
        return {}, [], 0, 0
    rows = [k[0] for k in grid.keys()]
    cols = [k[1] for k in grid.keys()]
    rmin, rmax = min(rows), max(rows)
    cmin, cmax = min(cols), max(cols)
    new_grid = {(r - rmin, c - cmin): v for (r, c), v in grid.items()}
    new_placements = []
    for word, r, c, d, cells in placements:
        ncells = [(rr - rmin, cc - cmin) for (rr, cc) in cells]
        new_placements.append((word, r - rmin, c - cmin, d, ncells))
    return new_grid, new_placements, rmax - rmin + 1, cmax - cmin + 1


def number_grid(grid: dict, placements: list) -> tuple[dict, list]:
    """Assign numbers to cells that begin a word (across or down).
    Returns (cell_to_number, [(number, word, direction, clue, cell)])."""
    starts = {}
    for word, r, c, d, cells in placements:
        starts.setdefault((r, c), []).append((word, d))
    sorted_starts = sorted(starts.keys())
    cell_to_number = {cell: i + 1 for i, cell in enumerate(sorted_starts)}
    return cell_to_number


def render_grid_image(
    grid: dict,
    cell_to_number: dict,
    rows: int,
    cols: int,
    out_path: Path,
    cell_px: int = 36,
) -> None:
    pad = 12
    W = cols * cell_px + pad * 2
    H = rows * cell_px + pad * 2
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    try:
        font_letter = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(cell_px * 0.55)
        )
        font_num = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(cell_px * 0.30)
        )
    except OSError:
        font_letter = ImageFont.load_default()
        font_num = ImageFont.load_default()

    for r in range(rows):
        for c in range(cols):
            x = pad + c * cell_px
            y = pad + r * cell_px
            if (r, c) in grid:
                draw.rectangle([x, y, x + cell_px, y + cell_px], fill="white", outline="#0A1F3D", width=2)
                num = cell_to_number.get((r, c))
                if num is not None:
                    draw.text((x + 3, y + 1), str(num), fill="#C8102E", font=font_num)
                # Letters intentionally hidden — solver puzzle. Uncomment below to print solutions.
                # draw.text((x + cell_px / 2 - 5, y + cell_px / 2 - 8), grid[(r, c)], fill="black", font=font_letter)
            else:
                draw.rectangle([x, y, x + cell_px, y + cell_px], fill="#0A1F3D", outline="#0A1F3D", width=2)

    img.save(str(out_path), optimize=True)


def build_clue_lists(placements: list, cell_to_number: dict, words: list[dict]) -> dict:
    word_to_clue = {w["word"].upper(): w.get("clue", "") for w in words}
    across, down = [], []
    for word, r, c, d, cells in placements:
        num = cell_to_number[(r, c)]
        entry = {"number": num, "word": word, "clue": word_to_clue.get(word, "")}
        if d == "H":
            across.append(entry)
        else:
            down.append(entry)
    across.sort(key=lambda e: e["number"])
    down.sort(key=lambda e: e["number"])
    return {"across": across, "down": down}


def main() -> None:
    if len(sys.argv) < 4:
        print("Usage: crossword_gen.py words.json out_image.png out_clues.json", file=sys.stderr)
        sys.exit(1)
    words_path = Path(sys.argv[1])
    image_out = Path(sys.argv[2])
    clues_out = Path(sys.argv[3])

    payload = json.loads(words_path.read_text())
    words = payload.get("words", [])
    seed = payload.get("seed")
    rng = random.Random(seed)

    grid, placements = build_grid(words, rng)
    grid, placements, rows, cols = normalize_grid(grid, placements)
    if rows > GRID_MAX or cols > GRID_MAX:
        # Trim layout if absurdly wide; in practice greedy keeps it tight
        pass
    cell_to_number = number_grid(grid, placements)

    image_out.parent.mkdir(parents=True, exist_ok=True)
    render_grid_image(grid, cell_to_number, rows, cols, image_out)

    clue_data = build_clue_lists(placements, cell_to_number, words)
    clue_data["meta"] = {
        "rows": rows,
        "cols": cols,
        "placed": len(placements),
        "skipped": [w["word"] for w in words if w.get("_skipped")],
    }
    clues_out.parent.mkdir(parents=True, exist_ok=True)
    clues_out.write_text(json.dumps(clue_data, indent=2))
    print(f"Wrote {image_out} and {clues_out} ({len(placements)} words placed, grid {rows}x{cols})")


if __name__ == "__main__":
    main()
