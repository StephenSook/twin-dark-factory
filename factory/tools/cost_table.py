"""Per-seat token and cost table for one room, from Band's own usage records.

  jam usage sessions --json > sessions.json      (on the machine that ran the seats)
  python cost_table.py sessions.json <room-id>

Dollar figures are Band's catalog-estimated equivalents at public list prices ("estimated_equivalent"
in the export), not provider billing. The seats ran on flat-rate subscriptions.
"""
import collections
import json
import sys

FIELDS = ("inputTokens", "outputTokens", "cacheCreationTokens", "cacheReadTokens")


def main():
    path, room = sys.argv[1], sys.argv[2]
    sessions = json.load(open(path))["sessions"]
    seats = collections.defaultdict(lambda: {"models": set(), "sessions": 0, "cost": 0.0, **{f: 0 for f in FIELDS}})
    for s in sessions:
        att = s.get("attribution") or {}
        if room not in (att.get("chatIds") or [att.get("chatId")]):
            continue
        row = seats[(att.get("peerName") or "unattributed").split("/")[-1]]
        row["sessions"] += 1
        row["cost"] += s.get("totalCost") or 0.0
        row["models"].update(m["model"] for m in s.get("models") or [])
        for f in FIELDS:
            row[f] += s.get(f) or 0
    if not seats:
        sys.exit(f"NO SESSIONS for room {room}: check the room id and that usage was captured")
    head = "| Seat | Model | Sessions | Input | Output | Cache write | Cache read | Est. USD |"
    print(head + "\n|" + "---|" * 8)
    total = collections.Counter()
    for name, r in sorted(seats.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"| {name} | {', '.join(sorted(r['models']))} | {r['sessions']} | "
              + " | ".join(f"{r[f]:,}" for f in FIELDS) + f" | {r['cost']:,.2f} |")
        total.update({f: r[f] for f in FIELDS})
        total["cost"] += r["cost"]
    print(f"| **Total** | | | " + " | ".join(f"{total[f]:,}" for f in FIELDS) + f" | {total['cost']:,.2f} |")
    print(f"\nAll tokens: {sum(total[f] for f in FIELDS):,}. Estimated list-price equivalent, not billing.")


if __name__ == "__main__":
    main()
