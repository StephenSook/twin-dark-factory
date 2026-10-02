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


def parse_pdf_urls(output):
    """URLs from `pdfinfo -url` rows: page, type, URL."""
    urls = set()
    for line in output.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3 and parts[0].isdigit():
            urls.add(parts[2].strip())
    return urls


def validate_pdf_links(pdf_urls, html_links):
    missing = sorted(set(html_links) - set(pdf_urls))
    if missing:
        raise RenderError("links not clickable in the PDF: " + ", ".join(missing))


def validate_page_text(page_texts):
    blank = [str(number) for number, text in enumerate(page_texts, start=1) if not text.strip()]
    if blank:
        raise RenderError("PDF pages without selectable text: " + ", ".join(blank))


def pdf_tool(arguments):
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        raise RenderError(f"{arguments[0]} is required to validate deck.pdf") from exc
    if result.returncode != 0:
        raise RenderError(f"{arguments[0]} failed: {result.stderr.strip() or 'no diagnostic'}")
    return result.stdout


def validate_pdf_content(path, page_count, html_links):
    validate_page_text([pdf_tool(["pdftotext", "-f", str(n), "-l", str(n), str(path), "-"])
                        for n in range(1, page_count + 1)])
    validate_pdf_links(parse_pdf_urls(pdf_tool(["pdfinfo", "-url", str(path)])), html_links)


LINKS_SCRIPT = "() => [...document.querySelectorAll('.slide a[href]')].map((a) => a.href)"


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


MIN_FONT_PX = 22
MIN_CONTRAST = 4.5
MIN_CONTRAST_LARGE = 3.0
LARGE_TEXT_PX = 32

QUALITY_SCRIPT = r"""
([minFont, largePx]) => {
  const parse = (value) => {
    const m = value.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map((x) => parseFloat(x));
    return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1};
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const background = (node) => {
    for (let n = node; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
    }
    return {r: 255, g: 255, b: 255, a: 1};
  };
  const ownText = (node) => [...node.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim());
  const visible = (node) => {
    const s = getComputedStyle(node);
    const r = node.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0;
  };
  const blocks = '.bignums > div, .card, .hook, .lead, .closeline, .check, .links, .seats, .caught, ' +
                 '.evidencecopy, .limits, .appduo, .draft, img, svg, h1, .note, .url, .kicker';
  const reports = [];
  document.querySelectorAll('.slide').forEach((slide, index) => {
    const issues = [];
    for (const img of slide.querySelectorAll('img')) {
      if (!img.complete || img.naturalWidth === 0) issues.push('broken image ' + img.getAttribute('src'));
    }
    for (const node of slide.querySelectorAll('*')) {
      if (!visible(node) || !ownText(node)) continue;
      const style = getComputedStyle(node);
      const size = parseFloat(style.fontSize);
      const sample = node.textContent.trim().slice(0, 40);
      if (size < minFont) issues.push(`text ${size}px below ${minFont}px: "${sample}"`);
      if (node instanceof SVGElement) continue;
      const fg = parse(style.color);
      if (!fg) continue;
      const bg = background(node);
      const [hi, lo] = [lum(fg), lum(bg)].sort((a, b) => b - a);
      const ratio = (hi + 0.05) / (lo + 0.05);
      const need = size >= largePx ? 3.0 : 4.5;
      if (ratio < need) issues.push(`contrast ${ratio.toFixed(2)} below ${need}: "${sample}"`);
    }
    const items = [...slide.querySelectorAll(blocks)].filter(visible);
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.contains(b) || b.contains(a)) continue;
        const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left);
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top);
        if (w <= 2 || h <= 2) continue;
        const smaller = Math.min(ra.width * ra.height, rb.width * rb.height);
        if (w * h > 0.01 * smaller) {
          const name = (n) => n.tagName.toLowerCase() + (n.className && n.className.baseVal === undefined && n.className ? '.' + String(n.className).split(' ')[0] : '');
          issues.push(`overlap ${name(a)} and ${name(b)}`);
        }
      }
    }
    if (issues.length) reports.push({slide: index + 1, issues});
  });
  return reports;
}
"""

SLIDE_TEXT_SCRIPT = "() => [...document.querySelectorAll('.slide')].map((s) => s.innerText)"

BANNED_COPY = {
    "—": "em dash", "–": "en dash", "“": "curly quote", "”": "curly quote",
    "‘": "curly quote", "’": "curly quote",
}
PLACEHOLDERS = re.compile(r"REQUIRED_|\bTODO\b|\bTBD\b|lorem ipsum|example\.(com|org)|example-|[{}]", re.I)
AI_TONE = re.compile(
    r"\b(delve|leverage[sd]?|robust|comprehensive|seamless(ly)?|powerful|transformative|elevate|empower|"
    r"intuitive|cutting-edge|revolutionary|amazing|effortless(ly)?|streamline[sd]?|unlocked|ecosystem)\b", re.I)


def lint_copy(slide_texts):
    """Refuse dashes, curly quotes, placeholders and AI-tone words in any slide's visible text."""
    problems = []
    for number, text in enumerate(slide_texts, start=1):
        for char, label in BANNED_COPY.items():
            if char in text:
                problems.append(f"slide {number}: {label}")
        for match in PLACEHOLDERS.finditer(text):
            problems.append(f"slide {number}: placeholder {match.group(0)!r}")
        for match in AI_TONE.finditer(text):
            problems.append(f"slide {number}: AI-tone word {match.group(0)!r}")
    if problems:
        raise RenderError("copy problems: " + "; ".join(sorted(set(problems))))


def validate_quality(reports):
    if reports:
        detail = "; ".join(f"slide {r['slide']}: " + ", ".join(r["issues"]) for r in reports)
        raise RenderError("visual quality problems: " + detail)


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
            validate_quality(page.evaluate(QUALITY_SCRIPT, [MIN_FONT_PX, LARGE_TEXT_PX]))
            lint_copy(page.evaluate(SLIDE_TEXT_SCRIPT))
            html_links = page.evaluate(LINKS_SCRIPT)

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
                validate_pdf_content(pdf, slide_count, html_links)

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
