# Twin: a dark factory that checks its work against an executable twin of the spec

Our factory for the WeAreDevelopers x BAND "Dark Factory" hackathon, pocketful track.

A band of five seats in BAND builds the product. The seats run on two model families.

- A **modeler** (Codex) turns the written requirements into an executable model, without ever
  reading the product code. The model is small, slow and obviously correct.
- A **builder** and a **surface** seat (Claude Code) build the product.
- A **gatekeeper** (Codex) accepts a revision only after it passes these checks:
  - it agrees with the model on random operation sequences
  - under 50 concurrent requests, the results can be explained by some one-at-a-time order
  - the stated invariants hold at every read
  - the checks catch faults deliberately planted in the code
- A **coordinator** (Claude Code) plans the work, pastes the full requirements into every
  handoff, and accepts only what the gatekeeper accepted.

The product code is written entirely by the band. This repository holds the factory: the
seats' mandates, how they are built, the guard that protects the result repository, the
dispatch, and the visual brief.

| Path | What it is |
|---|---|
| `factory/src/` | Mandate sources: one role file per seat, plus the working agreement every seat shares |
| `factory/seats.json` | Harness and model for each seat |
| `factory/mandates/` | Built mandates (`python factory/tools/build_mandates.py`) |
| `factory/tools/lint_mandates.py` | Fails if a mandate names track detail, using the organizers' vocabulary list |
| `factory/tools/pre-commit` | Result-repository guard. Commits are refused unless they come from a named seat. Seats may only change stage folders, and no commit may add a nested repository or cache files. |
| `factory/tools/test_pre_commit.sh` | Proves the guard both ways |
| `factory/dispatch/` | The task sent to the coordinator: the only human input to a run |
| `factory/design-kit/` | Visual brief and six illustrations supplied by the product owner |

## Checks

```sh
python factory/tools/build_mandates.py && git diff --exit-code -- factory/mandates
python factory/tools/lint_mandates.py <path-to-dark-factory-wearedevs> factory/mandates
sh factory/tools/test_pre_commit.sh
```

CI runs these checks on every push, together with a secret scan of the full history.

## Disclosure

- The seats are AI coding agents. Their harness and model are named at the top of each mandate.
- The illustrations in `factory/design-kit/art/` were generated for this project by the
  product owner and supplied to the band as assets.
- Fonts named in the brief are open-licensed.
