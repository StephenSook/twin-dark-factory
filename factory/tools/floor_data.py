"""Build floor.json for the Factory Floor page from a Band room export and the result repository.

Every number on the page is computed here from files anyone can download, so a reader can rerun
this script and get the same numbers.

  python floor_data.py <room.json> <result-repo or saved git log file> <out.json>
"""
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

MENTION = re.compile(r"@\[\[([0-9a-f-]{36})\]\]")
# A verdict is a message whose text, after any leading @mentions, starts with the verdict word
# and a revision (the form the mandates require). Quotes of an old verdict later in a message
# are not verdicts.
LEAD = re.compile(r"^(?:\s*@\[\[[0-9a-f-]{36}\]\])*[\s>*_#-]*")
VERDICT = re.compile(r"^`?(ACCEPT|REJECT)`?\s*`?([0-9a-f]{7,40})`?")
LINE_VERDICT = re.compile(r"(?m)^[\s>*_#-]*`?(ACCEPT|REJECT)`?\s+`?([0-9a-f]{7,40})`?")
STAGE_PATH = re.compile(r"^stage-(\d+)/")


def ts(s: str) -> float:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def load_room(path: pathlib.Path):
    raw = json.loads(path.read_text())
    msgs = sorted(raw["messages"], key=lambda m: m["insertedAt"])
    names = {}
    kinds = {}
    for m in msgs:
        kind = m.get("senderType", "Agent")
        name = m.get("senderName") or m["senderId"][:8]
        if kind == "Agent":
            name = name.rsplit("/", 1)[-1]
        names.setdefault(m["senderId"], name)
        kinds.setdefault(m["senderId"], kind)
    return raw, msgs, names, kinds


def delivery(meta) -> tuple[int, int]:
    """(extra attempts, failed recipients) from a message's delivery status."""
    extra = failed = 0
    status = (meta or {}).get("deliveryStatus") or {}
    for rec in status.values():
        attempts = rec.get("attempts") or []
        extra += max(0, len(attempts) - 1)
        if attempts and not any(a.get("completedAt") for a in attempts):
            failed += 1
    return extra, failed


GIT_FORMAT = "%H%x1f%an%x1f%aI%x1f%s"


def git_commits(repo: pathlib.Path):
    """Commits from a repository, or from a saved log file made with:
    git log --reverse --format='%H%x1f%an%x1f%aI%x1f%s' --name-only > commits.log"""
    if repo.is_file():
        out = repo.read_text()
    else:
        out = subprocess.run(["git", "-C", str(repo), "log", "--reverse", f"--format={GIT_FORMAT}", "--name-only"],
                             capture_output=True, text=True, check=True).stdout
    commits, cur = [], None
    for line in out.splitlines():
        if "\x1f" in line:
            h, a, t, s = line.split("\x1f", 3)
            cur = {"sha": h, "author": a, "t": ts(t), "subject": s, "stages": set()}
            commits.append(cur)
        elif line.strip() and cur is not None:
            mm = STAGE_PATH.match(line.strip())
            if mm:
                cur["stages"].add(int(mm.group(1)))
    for c in commits:
        c["stages"] = sorted(c["stages"])
    return commits


def declared_seats(repo: pathlib.Path):
    """Canonical seat names from the mandates committed in a result repository."""
    if repo.is_file():
        out = repo.read_text()
    else:
        out = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", "HEAD", "--", "mandates"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    return {
        pathlib.PurePosixPath(line).stem
        for line in out.splitlines()
        if re.fullmatch(r"mandates/[^/]+\.md", line)
    }


# Git records whole seconds and BAND records milliseconds, so a commit made in the same second as a
# room message can carry an earlier relative time. One second of slack keeps it on the right side.
CLOCK_SLACK_S = 1.0


def rejection_quote(preview):
    """The first sentence of a REJECT message, without its mentions and verdict prefix."""
    text = re.sub(r"^(\s*@\S+\s*)+", "", preview)
    text = re.sub(r"^`?REJECT`?\s*`?[0-9a-f]{7,40}`?:?\s*", "", text)
    text = re.split(r"\s+Reproduce\b", text)[0].strip()
    return re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]


def require_rejection_records(floor):
    """Fail with a fix, not a KeyError, on a floor.json written before rejection records existed."""
    totals = floor.get("totals") or {}
    needed = ("rejects_resolved_by_accepted_revision", "rejects_followed_by_seat_commit")
    if not isinstance(floor.get("rejections"), list) or any(key not in totals for key in needed):
        sys.exit("floor.json predates rejection records; regenerate it with tools/floor_data.py")


def featured_rejection(floor, facts):
    """The rejection the judge-facing copy shows: facts may name one, else the first with a follow-up."""
    require_rejection_records(floor)
    rejections = floor["rejections"]
    if not rejections:
        return None
    wanted = facts.get("featured_reject_rev")
    if wanted:
        named = [r for r in rejections if r["rev"] == wanted]
        if len(named) != 1:
            sys.exit(f"featured_reject_rev {wanted!r} is not exactly one rejection in floor.json")
        return named[0]
    return next((r for r in rejections if r["followup"]), rejections[0])


def gap_phrase(seconds):
    """Elapsed time in words for copy: never '0m'."""
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return "under a minute"
    hours, minutes = divmod(seconds // 60, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return "1 minute" if minutes == 1 else f"{minutes} minutes"


def rejection_record(commits, accepts, reject_t, revision, message_id):
    """What happened after one REJECT: the next writer commit in time and the accepted revision.

    `followup` is the earliest writer commit on a rejected stage made after the REJECT message.
    `resolved_by` is the first later ACCEPT of a newer revision whose writer commits since the
    rejected one, taken together, touch every rejected stage. A writer can push the revision that
    passes before the REJECT reaches the room, so the two answers differ and both are reported.
    Times compare unrounded (`t_exact`) values; the record publishes them rounded.
    """
    def exact(commit):
        return commit.get("t_exact", commit["t"])

    matches = [index for index, commit in enumerate(commits) if commit["sha"].startswith(revision)]
    record = {"rev": revision, "t": round(reject_t, 1), "message_id": message_id, "stages": [],
              "followup": None, "resolved_by": None}
    if len(matches) != 1:
        return record
    index = matches[0]
    stages = set(commits[index]["stages"])
    record["stages"] = sorted(stages)
    writers = [c for c in commits[index + 1:]
               if c["by_seat"] and c["author"] in ("builder", "surface") and stages.intersection(c["stages"])]
    later = [c for c in writers if exact(c) >= reject_t - CLOCK_SLACK_S]
    followup = min(later, key=exact) if later else None  # earliest in time, not log order
    if followup:
        record["followup"] = {"sha": followup["sha"], "t": round(exact(followup), 1),
                              "author": followup["author"], "subject": followup["subject"]}
    for accept_t, accept_rev, accept_id in sorted(accepts):
        if accept_t <= reject_t:
            continue
        hits = [j for j in range(index + 1, len(commits)) if commits[j]["sha"].startswith(accept_rev)]
        if len(hits) != 1 or not stages.intersection(commits[hits[0]]["stages"]):
            continue  # the accepted revision itself must be on a rejected stage
        covered = set()
        for c in commits[index + 1:hits[0] + 1]:
            if c["by_seat"] and c["author"] in ("builder", "surface"):
                covered.update(c["stages"])
        if stages.issubset(covered):
            record["resolved_by"] = {"rev": accept_rev, "t": round(accept_t, 1), "message_id": accept_id}
            break
    return record


def main():
    room_path, repo, out = map(pathlib.Path, sys.argv[1:4])
    raw, msgs, names, kinds = load_room(room_path)
    # The console export holds only the messages the page has loaded. A complete export starts
    # with the human's dispatch; anything else is truncated and every number would be wrong.
    first_text = next((m for m in msgs if m["messageType"] == "text"), None)
    if first_text is None or first_text.get("senderType") == "Agent":
        at = first_text["insertedAt"] if first_text else "none"
        sys.exit(f"TRUNCATED EXPORT: the first text message ({at}) is from an agent, not the human "
                 "dispatch. Scroll the room to its first message in the console, then download again.")
    # Room creation and join events can precede the run by minutes. Every elapsed-time claim is
    # measured from the human dispatch, which is the factory's actual start boundary.
    t0 = ts(first_text["insertedAt"])
    seats = {i: n for i, n in names.items() if kinds.get(i) == "Agent"}
    humans = {i: n for i, n in names.items() if kinds.get(i) != "Agent"}

    events, per_seat = [], {n: {"text": 0, "tool_call": 0, "thought": 0, "error": 0} for n in seats.values()}
    exact_t = {}  # unrounded message times for ordering; events publish them rounded
    retries = failed = 0
    for m in msgs:
        kind = m["messageType"]
        who = names.get(m["senderId"], "?")
        if who in per_seat and kind in per_seat[who]:
            per_seat[who][kind] += 1
        meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
        r, f = delivery(meta)
        retries += r
        failed += f
        if kind not in ("text", "error"):
            continue
        body = m.get("content") or ""
        to = [names.get(x, x[:8]) for x in MENTION.findall(body)]
        # Only the gatekeeper can make an authoritative acceptance decision. Other seats use
        # ACCEPT and REJECT while reporting model checks or relaying a verdict, and counting
        # those messages would invent extra stage boundaries in FACTORY.md and the deck.
        found = []
        if who == "gatekeeper":
            head = VERDICT.match(LEAD.sub("", body, count=1))
            if head:
                found.append(head.groups())
            found += LINE_VERDICT.findall(body)
        verdicts = [{"verdict": v, "rev": rev[:7]} for v, rev in dict.fromkeys(found)]
        exact_t[m["id"]] = ts(m["insertedAt"]) - t0
        events.append({
            "id": m["id"], "t": round(exact_t[m["id"]], 1), "from": who,
            "human": m["senderId"] in humans, "kind": kind, "to": sorted(set(to)),
            "chars": len(body), "verdicts": verdicts,
            "preview": MENTION.sub(lambda x: "@" + names.get(x.group(1), "?"), body)[:220],
        })

    duration_s = ts(msgs[-1]["insertedAt"]) - t0
    repository_commits = git_commits(repo)
    seat_names = declared_seats(repo)
    for c in repository_commits:
        relative_time = c["t"] - t0
        # Git records seconds while BAND records milliseconds. Time is display-only, so clamp
        # it to the observed room window. Stage paths and Git order define run membership.
        c["t"] = round(max(0.0, min(relative_time, duration_s)), 1)
        c["t_exact"] = relative_time  # unclamped, for follow-up order and elapsed time only
        c["by_seat"] = c["author"] in seat_names
    commits = [c for c in repository_commits if c["stages"]]
    stage_first = {}
    for c in commits:
        for s in c["stages"]:
            if c["by_seat"]:
                stage_first.setdefault(s, c["t"])
    # One decision per (verdict, revision): the same verdict sent to two seats counts once.
    first = {}
    for e in events:
        for v in e["verdicts"]:
            first.setdefault((v["verdict"], v["rev"]), (e["t"], e["id"]))
    accepts = [(t, rev) for (vd, rev), (t, _) in first.items() if vd == "ACCEPT"]
    rejects = [(t, rev, mid) for (vd, rev), (t, mid) in first.items() if vd == "REJECT"]
    accepts_with_ids = [(exact_t[mid], rev, mid) for (vd, rev), (_t, mid) in first.items() if vd == "ACCEPT"]
    rejections = [rejection_record(commits, accepts_with_ids, exact_t[mid], revision, mid)
                  for _t, revision, mid in sorted(rejects, key=lambda r: (exact_t[r[2]], r[1]))]
    changed = sum(1 for r in rejections if r["followup"])
    resolved = sum(1 for r in rejections if r["resolved_by"])
    handoffs = [e for e in events if not e["human"] and e["to"]]
    human_after_dispatch = [e for e in events if e["human"]][1:]

    floor = {
        "generated_from": {"room": room_path.name, "room_id": (raw.get("room") or {}).get("id"),
                           "exported_at": raw.get("exportedAt"), "messages": len(msgs)},
        "duration_s": round(duration_s, 1),
        "seats": sorted(seats.values()),
        "per_seat": per_seat,
        "totals": {
            "handoffs": len(handoffs),
            "handoff_chars_median": sorted(e["chars"] for e in handoffs)[len(handoffs) // 2] if handoffs else 0,
            "rejects": len(rejects), "rejects_followed_by_seat_commit": changed,
            "rejects_resolved_by_accepted_revision": resolved, "accepts": len(accepts),
            "human_messages_after_dispatch": len(human_after_dispatch),
            "delivery_retries": retries, "delivery_failures": failed,
            "commits": len(commits), "seat_commits": sum(c["by_seat"] for c in commits),
        },
        "stage_first_commit_s": stage_first,
        "events": events,
        "rejections": rejections,
        "commits": [{k: c[k] for k in ("sha", "author", "t", "subject", "stages", "by_seat")} for c in commits],
    }
    out.write_text(json.dumps(floor, indent=1))
    print(json.dumps(floor["totals"], indent=1))


if __name__ == "__main__":
    main()
