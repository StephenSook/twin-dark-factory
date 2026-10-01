#!/usr/bin/env python3
"""Require a BAND participant listing to contain exactly the configured agent handles."""
import json
import pathlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: check_room_participants.py <seats.json>")
configured = json.loads(pathlib.Path(sys.argv[1]).read_text())
expected = list(configured) if isinstance(configured, dict) else configured
if not isinstance(expected, list) or not expected or not all(isinstance(x, str) and x for x in expected):
    raise SystemExit("seats.json must contain a nonempty object or array of handle names")

agent_line = re.compile(r"^(\S+)\s+\[[^]]+\].*\(Agent;\s+id=[0-9a-f-]{36}\)$")
observed = []
unparsed = []
for line in sys.stdin.read().splitlines():
    if "(Agent;" not in line:
        continue
    match = agent_line.match(line)
    if match is None:
        unparsed.append(line)
        continue
    observed.append(match.group(1).rsplit("/", 1)[-1])

if unparsed:
    raise SystemExit(f"could not parse {len(unparsed)} agent participant lines")
if len(observed) != len(set(observed)):
    raise SystemExit("room has duplicate agent handles")
missing = sorted(set(expected) - set(observed))
extra = sorted(set(observed) - set(expected))
if missing or extra or len(observed) != len(expected):
    raise SystemExit(f"room agents differ: missing={missing} extra={extra}")
print(f"room has exactly {len(expected)} configured agents: {' '.join(sorted(observed))}")
