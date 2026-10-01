#!/usr/bin/env python3
"""Mutation checks for the deck renderer's validation gates."""

import importlib.util
import pathlib
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
RENDERER = ROOT / "factory" / "deck" / "render_deck.py"
spec = importlib.util.spec_from_file_location("render_deck", RENDERER)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def expect_error(label, action, text):
    try:
        action()
    except renderer.RenderError as exc:
        if text not in str(exc):
            raise AssertionError(f"{label}: wrong error: {exc}") from exc
    else:
        raise AssertionError(f"{label}: mutation was accepted")


expect_error(
    "zero slides",
    lambda: renderer.expected_slide_names(0),
    "zero slides",
)
expect_error(
    "reported overflow",
    lambda: renderer.validate_overflow([{"slide": 2, "reasons": ["child bounds"]}]),
    "slide overflow detected: 2",
)
expect_error(
    "missing PDF page count",
    lambda: renderer.parse_pdfinfo_pages("Title: deck\n"),
    "did not contain a page count",
)
expect_error(
    "wrong PDF page count",
    lambda: renderer.validate_pdf_page_count(2, 3),
    "expected 3, found 2",
)
assert renderer.parse_pdfinfo_pages("Title: deck\nPages:          12\n") == 12

with tempfile.TemporaryDirectory() as tmp_value:
    tmp = pathlib.Path(tmp_value)
    (tmp / "s01.png").write_bytes(b"png-one")
    (tmp / "s02.png").write_bytes(b"png-two")
    renderer.validate_slide_inventory(tmp, 2, require_complete=True)
    renderer.validate_outputs([tmp / "s01.png", tmp / "s02.png"])

    (tmp / "s03.png").write_bytes(b"stale")
    expect_error(
        "stale slide PNG",
        lambda: renderer.validate_slide_inventory(tmp, 2, require_complete=True),
        "stale or extra slide PNGs: s03.png",
    )
    (tmp / "s03.png").unlink()

    (tmp / "s02.png").unlink()
    expect_error(
        "missing slide PNG",
        lambda: renderer.validate_slide_inventory(tmp, 2, require_complete=True),
        "missing slide PNGs: s02.png",
    )
    renderer.validate_slide_inventory(tmp, 2, require_complete=False)

    (tmp / "s02.png").write_bytes(b"")
    expect_error(
        "empty slide PNG",
        lambda: renderer.validate_outputs([tmp / "s01.png", tmp / "s02.png"]),
        "empty render outputs: s02.png",
    )
    expect_error(
        "missing render output",
        lambda: renderer.validate_outputs([tmp / "deck.pdf"]),
        "missing render outputs: deck.pdf",
    )

print("ok   deck renderer refuses zero slides, overflow, stale outputs and page drift")
