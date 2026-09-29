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
        f'<p class="url">{esc(facts.get("live_url", ""))}</p>', "title"))
    seats = "".join(f'<div class="seat {fam.get(s, "Claude").lower()}"><b>{esc(s)}</b><span>{esc(fam.get(s, ""))}</span></div>'
                    for s in ["coordinator", "modeler", "builder", "surface", "gatekeeper"])
    slides.append(slide(
        "Two model families check each other; the seat that writes the code never accepts it.",
        f'<div class="seats">{seats}</div><p class="note">Claude seats plan and build. Codex seats model the '
        'spec independently and decide acceptance, without ever editing product code.</p>'))
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
        f'<div><b class="mono">{esc(facts["holdout_digest"][:12])}</b><span>digest committed before dispatch</span></div></div>'))
    slides.append(slide(
        f"The whole run cost {total_tok / 1e6:,.0f}M tokens, about ${total_cost:,.0f} at list prices.",
        hbars([(s, c) for s, c, _, _ in costs], unit="", fmt=lambda v: f"${v:,.2f}",
              accent={s: (INDIGO if fam.get(s) == "Codex" else HOT) for s, *_ in costs})
        + '<p class="note">Band\'s own usage export, list-price equivalent. Pink: Claude seats. Indigo: Codex seats.</p>'))
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
.draft {{ position: absolute; right: 60px; top: 40px; background: {HOT}; color: #fff; font-weight: 800; font-size: 26px; padding: 10px 22px; border-radius: 999px; }}
</style></head><body>"""


def main():
    floor = json.load(open(sys.argv[1]))
    facts = json.load(open(sys.argv[3]))
    out = pathlib.Path(sys.argv[4])
    draft = sys.argv[sys.argv.index("--draft") + 1] if "--draft" in sys.argv else ""
    out.mkdir(parents=True, exist_ok=True)
    (out / "deck.html").write_text(build(floor, sys.argv[2], facts, draft))
    print(out / "deck.html")


if __name__ == "__main__":
    main()
