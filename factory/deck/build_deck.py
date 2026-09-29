"""Build the slide deck (16:9 HTML, then PDF) from the run's own files.

  python build_deck.py <floor.json> <usage-sessions.json> <facts.json> <out-dir> [--draft LABEL]

Every number comes from floor.json (floor_data.py), Band's usage export (jam usage sessions --json)
or facts.json (filled from verify_result.sh, check_room.py and seal_holdout.py output). Nothing is
typed in by hand. --draft stamps every slide so a development deck cannot be mistaken for the real one.
Slides follow the assertion-evidence structure: a one-sentence claim, then the visual that proves it.
"""
import collections
import html
import json
import pathlib
import sys

INK, BODY, PAGE = "#2B2270", "#0B0B0F", "#FFF8E7"
SUN, BUTTER, AQUA, PINK_T, INDIGO, HOT = "#FFD24A", "#FAED8F", "#A4F6F8", "#FFDBFD", "#3B308F", "#FF3D9A"
GREEN, RED, GREY = "#0E7A4B", "#C4271B", "#B9B3A6"


def esc(s):
    return html.escape(str(s))


def fmt_t(s):
    s = int(round(s))
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def hbars(rows, width=1500, unit="", accent=None, fmt=lambda v: f"{v:,.0f}"):
    """Horizontal bars with direct labels; rows = [(label, value)], largest first."""
    top = max(v for _, v in rows) or 1
    bar_h, gap, label_w = 64, 26, 290
    h = len(rows) * (bar_h + gap)
    out = [f'<svg viewBox="0 0 {width} {h}" width="{width}" height="{h}" role="img">']
    for i, (label, v) in enumerate(rows):
        y = i * (bar_h + gap)
        w = max(4, (width - label_w - 260) * v / top)
        color = (accent or {}).get(label, INDIGO)
        out.append(f'<text x="{label_w - 20}" y="{y + bar_h * 0.66}" text-anchor="end" class="lbl">{esc(label)}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.0f}" height="{bar_h}" rx="12" fill="{color}"/>')
        out.append(f'<text x="{label_w + w + 18:.0f}" y="{y + bar_h * 0.66}" class="val">{esc(fmt(v))}{esc(unit)}</text>')
    out.append("</svg>")
    return "".join(out)


def timeline(floor, width=1600):
    """REJECT/ACCEPT verdicts along run time, one lane per stage accept boundary."""
    dur = floor["duration_s"] or 1
    seen, marks = set(), []
    for e in floor["events"]:
        for v in e["verdicts"]:
            key = (v["verdict"], v["rev"])
            if key in seen:
                continue
            seen.add(key)
            marks.append((e["t"], v["verdict"], v["rev"]))
    x = lambda t: 60 + (width - 120) * t / dur
    out = [f'<svg viewBox="0 0 {width} 420" width="{width}" height="420" role="img">',
           f'<line x1="60" y1="210" x2="{width - 60}" y2="210" stroke="{INK}" stroke-width="6" stroke-linecap="round"/>']
    for stage, t in sorted(floor["stage_first_commit_s"].items(), key=lambda kv: kv[1]):
        out.append(f'<text x="{x(t):.0f}" y="400" text-anchor="middle" class="small">stage {esc(stage)} starts</text>')
        out.append(f'<line x1="{x(t):.0f}" y1="232" x2="{x(t):.0f}" y2="370" stroke="{GREY}" stroke-width="3" stroke-dasharray="8 8"/>')
    for i, (t, verdict, rev) in enumerate(sorted(marks)):
        up = verdict == "REJECT"
        cy = 120 if up else 300
        color = RED if up else GREEN
        out.append(f'<line x1="{x(t):.0f}" y1="210" x2="{x(t):.0f}" y2="{cy}" stroke="{color}" stroke-width="4"/>')
        out.append(f'<circle cx="{x(t):.0f}" cy="{cy}" r="26" fill="{color}"/>')
        out.append(f'<text x="{x(t):.0f}" y="{cy + 9}" text-anchor="middle" class="dot">{"R" if up else "A"}</text>')
        if not up:
            out.append(f'<text x="{x(t):.0f}" y="{cy + 64}" text-anchor="middle" class="small">{esc(fmt_t(t))}</text>')
    out.append(f'<text x="60" y="60" class="small">REJECT above the line, ACCEPT below. {len([m for m in marks if m[1] == "REJECT"])} rejections, {len([m for m in marks if m[1] == "ACCEPT"])} accepts, {esc(fmt_t(dur))} of work.</text>')
    out.append("</svg>")
    return "".join(out)


def seat_costs(sessions_path, room):
    rows = collections.defaultdict(lambda: [0.0, 0, set()])
    for s in json.load(open(sessions_path))["sessions"]:
        att = s.get("attribution") or {}
        if room not in (att.get("chatIds") or [att.get("chatId")]):
            continue
        r = rows[(att.get("peerName") or "?").split("/")[-1]]
        r[0] += s.get("totalCost") or 0.0
        r[1] += sum(s.get(k) or 0 for k in ("inputTokens", "outputTokens", "cacheCreationTokens", "cacheReadTokens"))
        r[2].update(m["model"] for m in s.get("models") or [])
    return sorted(((k, *v) for k, v in rows.items()), key=lambda r: -r[1])


ART = {"dir": None}


def art(name, cls):
    """An illustration from the art folder, or nothing when the image is absent."""
    d = ART["dir"]
    if d is None:
        return ""
    for ext in ("webp", "png"):
        if (d / f"{name}.{ext}").exists():
            return f'<img class="{cls}" src="art/{name}.{ext}" alt="">'
    return ""


def flow_svg(width=1640, height=600):
    def box(x, y, w, h, fill, title, sub):
        return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{fill}" stroke="{INK}" stroke-width="4"/>'
                f'<text x="{x + w / 2}" y="{y + h / 2 - 8}" text-anchor="middle" class="bt">{esc(title)}</text>'
                f'<text x="{x + w / 2}" y="{y + h / 2 + 34}" text-anchor="middle" class="bs">{esc(sub)}</text>')

    def arrow(x1, y1, x2, y2, color=INK, dash=""):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="6"{d} marker-end="url(#ah)"/>'

    return "".join([
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">',
        f'<defs><marker id="ah" markerUnits="userSpaceOnUse" markerWidth="26" markerHeight="26" refX="22" refY="13" orient="auto">'
        f'<path d="M0,0 L26,13 L0,26 z" fill="{INK}"/></marker><marker id="ahr" markerUnits="userSpaceOnUse" markerWidth="26" markerHeight="26" refX="22" refY="13" orient="auto"><path d="M0,0 L26,13 L0,26 z" fill="{RED}"/></marker></defs>',
        box(0, 260, 300, 140, BUTTER, "Written spec", "four stages"),
        box(440, 110, 480, 150, PINK_T, "The product", "builder + surface (Claude)"),
        box(440, 400, 480, 150, AQUA, "An executable model", "modeler (Codex), never reads the code"),
        box(1100, 255, 520, 150, AQUA, "gatekeeper (Codex)", "same random operations to both"),
        arrow(300, 305, 435, 200), arrow(300, 355, 435, 460),
        arrow(920, 190, 1095, 300), arrow(920, 470, 1095, 360),
        f'<text x="1360" y="450" text-anchor="middle" class="bs">50 requests at once, planted faults,</text>',
        f'<text x="1360" y="488" text-anchor="middle" class="bs">upgrades, security, the design brief</text>',
        f'<path d="M1360,250 C1360,90 1150,60 925,140" fill="none" stroke="{RED}" stroke-width="6" stroke-dasharray="14 10" marker-end="url(#ahr)"/>',
        f'<text x="1360" y="40" text-anchor="middle" class="bt" style="fill:{RED}">REJECT with a reproduction</text>',
        f'<text x="1360" y="570" text-anchor="middle" class="bt" style="fill:{GREEN}">ACCEPT only when they agree</text>',
        "</svg>"])


def caught_slide(floor):
    """The first rejection, in the gatekeeper's words, and the seat commit that fixed it."""
    import re
    first = next((e for e in floor["events"] for v in e["verdicts"] if v["verdict"] == "REJECT"), None)
    if first is None:
        return slide("No rejections in this run.", "")
    text = re.sub(r"^(\s*@\S+\s*)+", "", first["preview"])
    text = re.sub(r"^`?REJECT`?\s*`?[0-9a-f]{7,40}`?:?\s*", "", text).strip()
    text = re.split(r"\s+Reproduce\b", text)[0]
    if not text.endswith("."):
        text = text[: text.rfind(".") + 1] or text  # drop a sentence cut off by the preview limit
    rev = next(v["rev"] for v in first["verdicts"] if v["verdict"] == "REJECT")
    fix = next((c for c in floor["commits"] if c["by_seat"] and c["t"] > first["t"]
                and c["author"] in ("builder", "surface")), None)
    fix_html = (f'<div class="card fix"><div class="who">{esc(fix["author"])} fixed it, {esc(fmt_t(fix["t"] - first["t"]))} later</div>'
                f'<p>{esc(fix["subject"])}</p><div class="id">commit {esc(fix["sha"][:7])}</div></div>') if fix else ""
    return slide(
        "A bad result it caught: the gatekeeper refused, the builder fixed it.",
        f'<div class="caught"><div class="card rej"><div class="who">gatekeeper: REJECT {esc(rev)} at {esc(fmt_t(first["t"]))}</div>'
        f'<p>{esc(text)}</p><div class="id">room message {esc(first["id"])}</div></div>'
        f'<div class="arrowbig">&rarr;</div>{fix_html}</div>')


def slide(headline, body, cls="", kicker=""):
    k = f'<div class="kicker">{esc(kicker)}</div>' if kicker else ""
    return f'<section class="slide {cls}">{k}<h1>{esc(headline)}</h1><div class="body">{body}</div></section>'


def build(floor, sessions_path, facts, draft):
    T = floor["totals"]
    room = floor["generated_from"]["room_id"]
    costs = seat_costs(sessions_path, room)
    fam = {s: ("Codex" if any("gpt" in m for m in models) else "Claude") for s, _, _, models in costs}
    total_cost = sum(c for _, c, _, _ in costs)
    total_tok = sum(t for _, _, t, _ in costs)
    stages = facts["stage_claims"]
    slides = []
    slides.append(slide(
        "The builder never grades its own work.",
        f'<p class="lead">Twin is a BAND dark factory: five coding agents on two model families that turned '
        f'a four-stage payments spec into a working app with one dispatch and no human help.</p>'
        f'<div class="bignums"><div><b>{len(stages)}/4</b><span>stages reached</span></div>'
        f'<div><b>{T["human_messages_after_dispatch"]}</b><span>human messages after dispatch</span></div>'
        f'<div><b>{T["rejects"]}</b><span>bad results caught and fixed</span></div></div>'
        f'<p class="url">{esc(facts.get("live_url", ""))}</p>' + art("hero-factory", "hero"), "title"))
    seats = "".join(f'<div class="seat {fam.get(s, "Claude").lower()}">{art(f"seat-{s}", "icon")}'
                    f'<b>{esc(s)}</b><span>{esc(fam.get(s, ""))}</span></div>'
                    for s in ["coordinator", "modeler", "builder", "surface", "gatekeeper"])
    slides.append(slide(
        "Two model families check each other; the seat that writes the code never accepts it.",
        f'<div class="seats">{seats}</div><p class="note">Claude seats plan and build. Codex seats model the '
        'spec independently and decide acceptance, without ever editing product code.</p>'))
    slides.append(slide(
        "The spec is built twice, by two model families, and the two builds must agree.",
        flow_svg()))
    slides.append(caught_slide(floor))
    slides.append(slide(
        "Every rejection changed the work before the next stage began.",
        timeline(floor)))
    slides.append(slide(
        f"Each folder claims its own stage in the organizers' isolated run.",
        '<div class="bignums">' + "".join(f'<div><b>{esc(s)}</b><span>stage {i + 1}: {esc(v)}</span></div>'
                                          for i, (s, v) in enumerate(stages.items())) + "</div>"))
    slides.append(slide(
        facts["holdout_headline"],
        f'<div class="bignums"><div><b>{esc(facts["holdout_score"])}</b><span>hidden attacks passed</span></div>'
        f'<div><b class="mono">{esc(facts["holdout_digest"][:12])}</b><span>digest committed before dispatch</span></div></div>'
        + art("sealed-envelope", "corner")))
    slides.append(slide(
        f"The whole run cost {total_tok / 1e6:,.0f}M tokens, about ${total_cost:,.0f} at list prices.",
        hbars([(s, c) for s, c, _, _ in costs], unit="", fmt=lambda v: f"${v:,.2f}",
              accent={s: (INDIGO if fam.get(s) == "Codex" else HOT) for s, *_ in costs})
        + '<p class="note">Band\'s own usage export, list-price equivalent. Pink: Claude seats. Indigo: Codex seats.</p>'))
    if facts.get("limits"):
        slides.append(slide(
            "What it does not do yet.",
            '<ul class="limits">' + "".join(f"<li>{esc(x)}</li>" for x in facts["limits"]) + "</ul>"))
    slides.append(slide(
        "Check every number yourself.",
        '<ul class="check">' + "".join(f"<li><code>{esc(c)}</code></li>" for c in facts["check_commands"]) + "</ul>"))
    stamp = f'<div class="draft">{esc(draft)}</div>' if draft else ""
    return (PAGE_HEAD + "".join(s.replace("</section>", stamp + "</section>") for s in slides) + "</body></html>")


PAGE_HEAD = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=Figtree:wght@500;600;700&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<style>
@page {{ size: 1920px 1080px; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: {PAGE}; font-family: Figtree, sans-serif; color: {BODY}; }}
.slide {{ width: 1920px; height: 1080px; padding: 110px 140px; position: relative; page-break-after: always; overflow: hidden; background: {PAGE}; }}
.slide.title {{ background: {SUN}; }}
h1 {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 76px; line-height: 1.08; color: {INK}; margin: 0 0 60px; max-width: 1560px; }}
.kicker {{ font-weight: 700; color: {HOT}; font-size: 30px; margin-bottom: 18px; }}
.lead {{ font-size: 40px; line-height: 1.35; max-width: 1400px; color: {INK}; }}
.note {{ font-size: 28px; color: #4a4560; max-width: 1400px; }}
.url {{ position: absolute; bottom: 90px; font-size: 34px; font-weight: 700; color: {INK}; }}
.bignums {{ display: flex; gap: 60px; flex-wrap: wrap; margin-top: 30px; }}
.bignums div {{ background: #fff; border: 3px solid {INK}; border-radius: 28px; padding: 36px 48px; min-width: 330px; }}
.bignums b {{ display: block; font-family: 'Bricolage Grotesque'; font-size: 110px; color: {INK}; line-height: 1; }}
.bignums b.mono {{ font-family: 'JetBrains Mono', monospace; font-size: 64px; }}
.bignums span {{ font-size: 28px; font-weight: 600; }}
.seats {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 28px; margin: 20px 0 50px; }}
.seat {{ border-radius: 28px; padding: 40px 24px; text-align: center; border: 3px solid {INK}; }}
.seat.claude {{ background: {PINK_T}; }} .seat.codex {{ background: {AQUA}; }}
.seat b {{ display: block; font-family: 'Bricolage Grotesque'; font-size: 44px; color: {INK}; }}
.seat span {{ font-size: 28px; font-weight: 600; }}
svg .lbl, svg .val {{ font: 700 34px Figtree, sans-serif; fill: {INK}; }}
svg .small {{ font: 600 26px Figtree, sans-serif; fill: #4a4560; }}
svg .dot {{ font: 800 26px Figtree, sans-serif; fill: #fff; }}
.check {{ font-size: 32px; line-height: 1.9; }}
code {{ font-family: 'JetBrains Mono', monospace; background: #fff; border: 2px solid {INK}; border-radius: 10px; padding: 4px 12px; font-size: 26px; }}
img.hero {{ position: absolute; right: 90px; bottom: 60px; width: 620px; }}
img.corner {{ position: absolute; right: 150px; bottom: 90px; width: 440px; }}
img.icon {{ display: block; width: 150px; height: 150px; object-fit: contain; margin: 0 auto 14px; }}
svg .bt {{ font: 800 36px 'Bricolage Grotesque', sans-serif; fill: {INK}; }}
svg .bs {{ font: 600 26px Figtree, sans-serif; fill: #3a3550; }}
.caught {{ display: flex; align-items: stretch; gap: 40px; }}
.card {{ flex: 1; background: #fff; border: 4px solid {INK}; border-radius: 28px; padding: 40px 44px; }}
.card.rej {{ border-color: {RED}; }} .card.fix {{ border-color: {GREEN}; }}
.card .who {{ font: 800 32px 'Bricolage Grotesque', sans-serif; color: {INK}; margin-bottom: 18px; }}
.card p {{ font-size: 32px; line-height: 1.4; margin: 0 0 22px; }}
.card .id {{ font-family: 'JetBrains Mono', monospace; font-size: 22px; color: #6a6480; }}
.arrowbig {{ font-size: 110px; color: {INK}; align-self: center; }}
.limits {{ font-size: 36px; line-height: 1.6; max-width: 1500px; }}
.draft {{ position: absolute; right: 60px; top: 40px; background: {HOT}; color: #fff; font-weight: 800; font-size: 26px; padding: 10px 22px; border-radius: 999px; }}
</style></head><body>"""


def main():
    floor = json.load(open(sys.argv[1]))
    facts = json.load(open(sys.argv[3]))
    out = pathlib.Path(sys.argv[4])
    draft = sys.argv[sys.argv.index("--draft") + 1] if "--draft" in sys.argv else ""
    out.mkdir(parents=True, exist_ok=True)
    if "--art" in sys.argv:
        import shutil
        src = pathlib.Path(sys.argv[sys.argv.index("--art") + 1])
        shutil.copytree(src, out / "art", dirs_exist_ok=True)
        ART["dir"] = out / "art"
    (out / "deck.html").write_text(build(floor, sys.argv[2], facts, draft))
    print(out / "deck.html")


if __name__ == "__main__":
    main()
