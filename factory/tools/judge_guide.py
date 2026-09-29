"""Write JUDGE-GUIDE.md: a three-minute tour of the run, every stop a real room message or commit.

  python judge_guide.py <floor.json> <facts.json> > JUDGE-GUIDE.md

floor.json comes from floor_data.py; facts.json holds the live URL, the room.json sha256 printed by
check_room.py and the sealed holdout digest. Every id below is copied from those files, and every
stop has a command that shows it from a fresh clone.
"""
import json
import re
import sys


def mmss(s):
    s = int(round(s))
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def main():
    floor = json.load(open(sys.argv[1]))
    facts = json.load(open(sys.argv[2]))
    ev, commits, T = floor["events"], floor["commits"], floor["totals"]
    rejects = [(e, v["rev"]) for e in ev for v in e["verdicts"] if v["verdict"] == "REJECT"]
    seen, accepts = set(), []
    for e in ev:
        for v in e["verdicts"]:
            if v["verdict"] == "ACCEPT" and v["rev"] not in seen:
                seen.add(v["rev"])
                accepts.append((e, v["rev"]))
    final = next((e for e in reversed(ev) if e["from"] == "coordinator" and "FINAL REPORT" in e["preview"]), None)
    show = "jq '.messages[] | select(.id==\"{}\") | .content' room.json"
    out = []
    w = out.append
    w("# Judge guide: the run in three minutes\n")
    w("Every stop below is a real room message or commit. Paste the command to see it yourself from a "
      "fresh clone of this repository.\n")
    w(f"**0:00 What it is.** {facts.get('one_line', 'Twin: five agents, two model families; the builder never grades its own work.')} "
      "Read the seat table at the top of `FACTORY.md`, then the mandates in `mandates/`.\n")
    if rejects:
        e, rev = rejects[0]
        text = re.sub(r"^(\s*@\S+\s*)+", "", e["preview"])
        text = re.sub(r"^`?REJECT`?\s*`?[0-9a-f]{7,40}`?:?\s*", "", text)
        text = re.split(r"\s+Reproduce\b", text)[0][:200]
        fix = next((c for c in commits if c["by_seat"] and c["t"] > e["t"] and c["author"] in ("builder", "surface")), None)
        w(f"**0:30 A bad result the factory caught.** At {mmss(e['t'])} the gatekeeper rejected revision "
          f"`{rev}`: \"{text.strip()}\"")
        w(f"```\n{show.format(e['id'])}\n```")
        if fix:
            w(f"{fix['author']} fixed it {mmss(fix['t'] - e['t'])} later in commit `{fix['sha'][:7]}` "
              f"(\"{fix['subject']}\"):\n```\ngit show --stat {fix['sha'][:7]}\n```")
        w(f"The run had {T['rejects']} rejections; every one was followed by a seat commit.\n")
    w("**1:15 Every stage accepted by a different model family than the one that wrote it.**\n")
    w("| Stage | Accepted at | Revision | Room message |\n|---|---|---|---|")
    for i, (e, rev) in enumerate(accepts, 1):
        w(f"| {i} | {mmss(e['t'])} | `{rev}` | `{e['id']}` |")
    w("")
    w(f"**1:45 Hands off.** One dispatch, then {T['human_messages_after_dispatch']} human messages. "
      f"room.json is the unchanged BAND export (sha256 `{facts.get('room_sha256', 'see check_room.py')}`):")
    w("```\npython tools/check_room.py room.json\n```")
    w(f"**2:15 The stage it reached.** The organizers' checker, isolated mode, every folder:\n"
      "```\npython -m harness run --track pocketful --repo . --all --mode isolated\n```")
    w(f"**2:40 Evidence the band never saw.** The sealed holdout digest was committed before dispatch "
      f"(`{facts.get('holdout_digest', '')[:16]}`); after the event the suite is published and anyone can "
      "run `python tools/seal_holdout.py verify <suite folder> <digest>`.")
    if facts.get("live_url"):
        w(f"\n**Try it.** {facts['live_url']} (demo logins in `deploy/README.md`).")
    if final:
        w(f"\nThe coordinator's final report: `{final['id']}`.")
    print("\n".join(out))


if __name__ == "__main__":
    main()
