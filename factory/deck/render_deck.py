#!/usr/bin/env python3
"""Render and validate a 1920x1080 HTML slide deck.

Usage: render_deck.py <deck-dir>

The deck directory must contain deck.html. The renderer writes deck.pdf and one
sNN.png screenshot per ``.slide`` element. Validation finishes before those
files replace a prior render.
"""

import argparse
import os
import pathlib
import re
import subprocess
import tempfile


SLIDE_FILE = re.compile(r"s[0-9]+\.png")


class RenderError(RuntimeError):
    """The deck could not be rendered or did not pass validation."""


def expected_slide_names(slide_count):
    if slide_count <= 0:
        raise RenderError("deck contains zero slides")
    return {f"s{number:02d}.png" for number in range(1, slide_count + 1)}


def slide_names(directory):
    return {
        path.name
        for path in pathlib.Path(directory).iterdir()
        if path.is_file() and SLIDE_FILE.fullmatch(path.name)
    }


def validate_slide_inventory(directory, slide_count, require_complete):
    expected = expected_slide_names(slide_count)
    found = slide_names(directory)
    extra = sorted(found - expected)
    missing = sorted(expected - found) if require_complete else []
    if extra:
        raise RenderError("stale or extra slide PNGs: " + ", ".join(extra))
    if missing:
        raise RenderError("missing slide PNGs: " + ", ".join(missing))


def validate_outputs(paths):
    missing = []
    empty = []
    for path in map(pathlib.Path, paths):
        if not path.is_file():
            missing.append(path.name)
        elif path.stat().st_size == 0:
            empty.append(path.name)
    if missing:
        raise RenderError("missing render outputs: " + ", ".join(sorted(missing)))
    if empty:
        raise RenderError("empty render outputs: " + ", ".join(sorted(empty)))


def parse_pdfinfo_pages(output):
    match = re.search(r"^Pages:\s*([0-9]+)\s*$", output, re.MULTILINE)
    if not match:
        raise RenderError("pdfinfo output did not contain a page count")
    return int(match.group(1))


def pdf_page_count(path):
    try:
        result = subprocess.run(
            ["pdfinfo", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RenderError("pdfinfo is required to validate deck.pdf") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic"
        raise RenderError(f"pdfinfo failed: {detail}")
    return parse_pdfinfo_pages(result.stdout)


def validate_pdf_page_count(actual, expected):
    if actual != expected:
        raise RenderError(f"PDF page count mismatch: expected {expected}, found {actual}")


def validate_overflow(overflow):
    if overflow:
        slides = ", ".join(str(item["slide"]) for item in overflow)
        raise RenderError(f"slide overflow detected: {slides}")


OVERFLOW_SCRIPT = r"""
() => {
  const tolerance = 2;
  const reports = [];
  document.querySelectorAll('.slide').forEach((slide, index) => {
    const root = slide.getBoundingClientRect();
    const reasons = [];
    for (const node of slide.querySelectorAll('*')) {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (style.display === 'none' || style.visibility === 'hidden' ||
          (rect.width === 0 && rect.height === 0)) {
        continue;
      }
      if (rect.left < root.left - tolerance || rect.top < root.top - tolerance ||
          rect.right > root.right + tolerance || rect.bottom > root.bottom + tolerance) {
        reasons.push('child bounds');
        break;
      }
      const clipsX = style.overflowX !== 'visible' &&
        node.scrollWidth > node.clientWidth + tolerance;
      const clipsY = style.overflowY !== 'visible' &&
        node.scrollHeight > node.clientHeight + tolerance;
      if (node instanceof HTMLElement && (clipsX || clipsY)) {
        reasons.push('clipped child content');
        break;
      }
    }
    if (reasons.length) {
      reports.push({slide: index + 1, reasons});
    }
  });
  return reports;
}
"""


ASSET_WAIT_SCRIPT = r"""
async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map((image) => {
    if (image.complete) return image.decode().catch(() => {});
    return new Promise((resolve, reject) => {
      image.addEventListener('load', resolve, {once: true});
      image.addEventListener('error', reject, {once: true});
    });
  }));
}
"""


def render(deck_dir):
    deck_dir = pathlib.Path(deck_dir).resolve()
    deck_html = deck_dir / "deck.html"
    if not deck_dir.is_dir():
        raise RenderError(f"deck directory does not exist: {deck_dir}")
    if not deck_html.is_file():
        raise RenderError(f"missing deck.html: {deck_html}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RenderError("Playwright for Python is required to render the deck") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(deck_html.as_uri(), wait_until="networkidle")
            page.evaluate(ASSET_WAIT_SCRIPT)
            slides = page.locator(".slide")
            slide_count = slides.count()
            expected = expected_slide_names(slide_count)
            validate_slide_inventory(deck_dir, slide_count, require_complete=False)
            validate_overflow(page.evaluate(OVERFLOW_SCRIPT))

            with tempfile.TemporaryDirectory(prefix=".deck-render-", dir=deck_dir) as temp_value:
                temp = pathlib.Path(temp_value)
                pdf = temp / "deck.pdf"
                page.pdf(
                    path=str(pdf),
                    width="1920px",
                    height="1080px",
                    print_background=True,
                )
                for index, name in enumerate(sorted(expected)):
                    slides.nth(index).screenshot(path=str(temp / name))

                validate_slide_inventory(temp, slide_count, require_complete=True)
                outputs = [pdf, *(temp / name for name in sorted(expected))]
                validate_outputs(outputs)
                validate_pdf_page_count(pdf_page_count(pdf), slide_count)

                os.replace(pdf, deck_dir / "deck.pdf")
                for name in sorted(expected):
                    os.replace(temp / name, deck_dir / name)
        finally:
            browser.close()

    final_outputs = [deck_dir / "deck.pdf", *(deck_dir / name for name in sorted(expected))]
    validate_slide_inventory(deck_dir, slide_count, require_complete=True)
    validate_outputs(final_outputs)
    validate_pdf_page_count(pdf_page_count(deck_dir / "deck.pdf"), slide_count)
    print(f"rendered {slide_count} slides: {deck_dir / 'deck.pdf'}")


def main(argv=None):
    parser = argparse.ArgumentParser(usage="render_deck.py <deck-dir>")
    parser.add_argument("deck_dir")
    args = parser.parse_args(argv)
    try:
        render(args.deck_dir)
    except RenderError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
