# Twin: a dark factory that checks its work against an executable twin of the spec

Our factory for the WeAreDevelopers x BAND "Dark Factory" hackathon, pocketful track.

## What it built

The judged run is in its own repository: https://github.com/StephenSook/twin-pocketful-judged.
One dispatch, then no human message: the band reached all four Pocketful stages, and every
number below is generated there from the room export and git, never typed.

- Result README, with the measured run, the independent checks and how to reproduce them:
  https://github.com/StephenSook/twin-pocketful-judged#readme
- Live app (free hosting, the first visit after an idle spell can take about a minute):
  https://twin-pocketful-judged-demo.onrender.com/
- Factory Floor, a replay of the whole room: https://stephensook.github.io/twin-pocketful-judged/
- Demo film, with the Band Desktop room recording: https://youtu.be/f4lin76MaG4

A band of six seats in BAND builds the product. The seats run on three model families.

- A **modeler** (Codex) turns the written requirements into an executable model, without ever
  reading the product code. The model is small, slow and obviously correct.
- A **builder** and a **surface** seat (Claude Code) build the product.
- A **gatekeeper** (Codex) accepts a revision only after it passes these checks:
  - it agrees with the model on random operation sequences
  - under 50 concurrent requests, the results can be explained by some one-at-a-time order
  - the stated invariants hold at every read
  - the checks catch faults deliberately planted in the code
- An **auditor** (OpenCode with DeepSeek on Featherless) compares the written requirements with
  the modeler's ledger without reading product code, looking for shared misreadings that would
  change the product's behaviour.
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
| `factory/tools/seal_holdout.py` | Commit-then-reveal for a holdout check suite the band never sees: seal a digest before a run, publish the files after, anyone verifies |
| `factory/dispatch/` | The task sent to the coordinator: the only human input to a run |
| `factory/design-kit/` | Visual brief and six illustrations supplied by the product owner |
| `factory/deck/` | Evidence-fed deck builder and renderer. Rendering fails on overflow, missing slides, stale images, empty files or PDF page drift. |
| `factory/tools/check_room.py` | Checks that `room.json` is a complete, unedited BAND export of an unattended run, with the expected acceptances |
| `factory/tools/floor_data.py`, `factory/floor/` | Builds the Factory Floor replay data from the room export and git, and the page that plays it |
| `factory/tools/factory_md.py`, `result_readme.py`, `judge_guide.py` | Generate the result repository's FACTORY.md, README and JUDGE-GUIDE from the run's own files; a missing fact is an error, never a blank |
| `factory/tools/check_claim_evidence.py`, `check_public_copy.py` | Every central claim cites a distinct room message; public pages carry no placeholder, banned typography or AI-tone word |
| `factory/tools/verify_result.sh` | Verifies a result repository the way a judge would: fresh clone, the organizers' checker, isolated mode |

## Checks

```sh
python factory/tools/build_mandates.py && git diff --exit-code -- factory/mandates
python factory/tools/lint_mandates.py <path-to-dark-factory-wearedevs> factory/mandates
python factory/tools/test_deck_renderer.py
sh factory/tools/test_pre_commit.sh
```

CI (`.github/workflows/ci.yml`) runs these and every other tool's tests on every push, together
with a secret scan of the full history.

## Disclosure

- The seats are AI coding agents. Their harness and model are named at the top of each mandate.
- The illustrations in `factory/design-kit/art/` were generated for this project by the
  product owner and supplied to the band as assets.
- Fonts named in the brief are open-licensed.
- The presenter in the demo film is an AI avatar of me with a clone of my voice, made with HeyGen;
  the screen recordings, the room and the live app are real.
