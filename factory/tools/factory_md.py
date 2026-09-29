"""Generate FACTORY.md from the run's own files, so no number is typed by hand.

  python factory_md.py --repo <result repo> --floor floor.json --sessions usage-sessions.json \
      --facts facts.json [--template FACTORY.template.md] [--draft] > FACTORY.md

Seats and models come from the committed mandates' Harness and Model lines; mandate fingerprints
from their bytes; verdicts, times and hands-off counts from floor.json (floor_data.py); tokens and
dollars from Band's usage export; stage claims, holdout, genericity, baseline, checks and limits
from facts.json, which is filled from the outputs of verify_result.sh, seal_holdout.py and the
other runs. Without --draft a missing fact is an error, never a blank.
"""
import argparse
import collections
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
OWNS = {
    "coordinator": ("the plan, handoffs carrying the full requirements, stage copy-forward, stall recovery, final report", "write product code or checks"),
    "modeler": ("the requirement ledger, the executable model, the differential driver", "read product code"),
    "builder": ("the service, storage, concurrency, the container", "accept its own work"),
    "surface": ("the browser interface and its states, screenshots at two widths", "touch service rules"),
    "gatekeeper": ("clean-copy reruns, isolated checks, concurrency histories, planted faults, security, ACCEPT or REJECT", "edit product code"),
    "auditor": ("a third reading of the requirements against the ledger", "read or write product code"),
}
MISSING = []


def need(facts, key, draft):
    if key in facts and facts[key] not in (None, "", [], {}):
        return facts[key]
    MISSING.append(key)
    return "NOT MEASURED YET" if draft else None


def mmss(s):
    s = int(round(s))
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def seats_table(repo):
    rows = ["| Seat | Harness | Model | Owns | Never |", "|---|---|---|---|---|"]
    for f in sorted((repo / "mandates").glob("*.md")):
        head = f.read_text().splitlines()[:3]
        harness = next((l.split(":", 1)[1].strip() for l in head if l.startswith("Harness:")), "?")
        model = next((l.split(":", 1)[1].strip() for l in head if l.startswith("Model:")), "?")
        owns, never = OWNS.get(f.stem, ("", ""))
        rows.append(f"| {f.stem} | {harness} | {model} | {owns} | {never} |")
    return "\n".join(rows)


def hashes(repo):
    return "\n".join(f"- `mandates/{f.name}`: `{hashlib.sha256(f.read_bytes()).hexdigest()}`"
                     for f in sorted((repo / "mandates").glob("*.md")))


def verdicts(floor):
    rows = ["| At | Verdict | Revision | What the gatekeeper said | Room message |", "|---|---|---|---|---|"]
    seen = set()
    for e in floor["events"]:
        for v in e["verdicts"]:
            key = (v["verdict"], v["rev"])
            if key in seen:
                continue
            seen.add(key)
            text = re.sub(r"^(\s*@\S+\s*)+", "", e["preview"])
            text = re.sub(r"^`?(ACCEPT|REJECT)`?\s*`?[0-9a-f]{7,40}`?:?\s*", "", text)
            text = re.split(r"\s+Reproduce\b", text)[0].replace("|", "/")[:120]
            rows.append(f"| {mmss(e['t'])} | {v['verdict']} | `{v['rev']}` | {text} | `{e['id'][:8]}` |")
    return "\n".join(rows)


def first_catch(floor):
    for e in floor["events"]:
        for v in e["verdicts"]:
            if v["verdict"] != "REJECT":
                continue
            text = re.sub(r"^(\s*@\S+\s*)+", "", e["preview"])
            text = re.sub(r"^`?REJECT`?\s*`?[0-9a-f]{7,40}`?:?\s*", "", text)
            text = re.split(r"\s+Reproduce\b", text)[0].strip()
            fix = next((c for c in floor["commits"] if c["by_seat"] and c["t"] > e["t"]
                        and c["author"] in ("builder", "surface")), None)
            tail = (f" {fix['author']} fixed it {mmss(fix['t'] - e['t'])} later in `{fix['sha'][:7]}` "
                    f"(\"{fix['subject']}\").") if fix else ""
            return f"at {mmss(e['t'])} the gatekeeper rejected `{v['rev']}`: \"{text}\" (room message `{e['id']}`).{tail}"
    return "no rejection in this run."


def costs(sessions_path, room, facts, draft):
    rows = collections.defaultdict(lambda: [set(), 0, 0.0])
    for s in json.load(open(sessions_path))["sessions"]:
        att = s.get("attribution") or {}
        if room not in (att.get("chatIds") or [att.get("chatId")]):
            continue
        r = rows[(att.get("peerName") or "unattributed").split("/")[-1]]
        r[0].update(m["model"] for m in s.get("models") or [])
        r[1] += sum(s.get(k) or 0 for k in ("inputTokens", "outputTokens", "cacheCreationTokens", "cacheReadTokens"))
        r[2] += s.get("totalCost") or 0.0
    out = ["| Seat | Model | Tokens | List-price equivalent (USD) |", "|---|---|---|---|"]
    for seat, (models, tok, usd) in sorted(rows.items(), key=lambda kv: -kv[1][2]):
        out.append(f"| {seat} | {', '.join(sorted(models))} | {tok:,} | {usd:,.2f} |")
    tok = sum(v[1] for v in rows.values())
    usd = sum(v[2] for v in rows.values())
    out.append(f"| **total** | | {tok:,} | {usd:,.2f} |")
    fl = need(facts, "featherless_usd", draft)
    out.append("\nThe Claude and Codex seats ran on flat-rate subscriptions; the dollars above are Band's "
               "own list-price estimate from its usage export, not a bill. The auditor ran on Featherless "
               f"credits, metered: **${fl}** for the whole run." if fl is not None else "")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    for a in ("--repo", "--floor", "--sessions", "--facts"):
        ap.add_argument(a, required=True)
    ap.add_argument("--template", default=str(HERE.parent / "docs" / "FACTORY.template.md"))
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    repo, floor, facts = pathlib.Path(a.repo), json.load(open(a.floor)), json.load(open(a.facts))
    T = floor["totals"]
    room = floor["generated_from"]["room_id"]
    accepts, seen = [], set()
    for e in floor["events"]:
        for v in e["verdicts"]:
            if v["verdict"] == "ACCEPT" and v["rev"] not in seen:
                seen.add(v["rev"])
                accepts.append((e, v["rev"]))
    claims = need(facts, "stage_claims", a.draft)
    holdout = need(facts, "holdout_score", a.draft)
    generic = need(facts, "genericity", a.draft)
    baseline = need(facts, "baseline", a.draft)
    results = [
        f"- **Stage reached.** The organizers' checker in isolated mode on a fresh clone: "
        + (", ".join(f"stage {k} {v}" for k, v in claims.items()) if isinstance(claims, dict) else str(claims)) + ".",
        f"- **Hands off.** {T['human_messages_after_dispatch']} human messages after the dispatch; "
        f"room.json sha256 `{need(facts, 'room_sha256', a.draft)}`.",
        f"- **Evidence the band never saw.** Sealed holdout digest `{facts.get('holdout_digest', '')[:16]}` "
        f"committed before dispatch; score after the run: **{holdout}**.",
        f"- **Generic.** {generic if isinstance(generic, str) else json.dumps(generic)}",
        f"- **One agent against the band.** {baseline if isinstance(baseline, str) else json.dumps(baseline)}",
    ]
    fill = {
        "{{SEATS_TABLE}}": seats_table(repo),
        "{{MANDATE_HASHES}}": hashes(repo),
        "{{CATCH_STATS}}": (f"{T['rejects']} rejections and {T['accepts']} acceptances over {T['handoffs']} handoffs; "
                            f"{T['rejects_followed_by_seat_commit']} of the {T['rejects']} rejections were followed by a seat commit. "
                            f"{T['seat_commits']} of {T['commits']} commits were made by seats."),
        "{{VERDICT_TABLE}}": verdicts(floor),
        "{{FIRST_CATCH}}": first_catch(floor),
        "{{COST_TABLE}}": costs(a.sessions, room, facts, a.draft),
        "{{STAGE_TIMES}}": "Wall time from dispatch: " + ", ".join(f"stage {i} accepted at {mmss(e['t'])}" for i, (e, _) in enumerate(accepts, 1))
                           + f"; the whole run took {mmss(floor['duration_s'])}.",
        "{{RESULTS}}": "\n".join(results),
        "{{CHECKS}}": "```\n" + "\n".join(need(facts, "check_commands", a.draft) or []) + "\n```",
        "{{LIMITS}}": "\n".join(f"- {x}" for x in (need(facts, "limits", a.draft) or [])),
    }
    text = pathlib.Path(a.template).read_text()
    for k, v in fill.items():
        text = text.replace(k, str(v))
    left = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if left:
        sys.exit(f"unfilled placeholders: {left}")
    if MISSING and not a.draft:
        sys.exit(f"missing facts (run without --draft only when every fact is measured): {sorted(set(MISSING))}")
    if a.draft:
        text = "> DRAFT: generated from development data; facts marked NOT MEASURED YET are pending.\n\n" + text
    sys.stdout.write(text)


if __name__ == "__main__":
    main()
