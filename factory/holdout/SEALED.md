# Sealed holdout

A private attack suite the band never sees: 73 attacks across the four pocketful stages
(16 for stage 1, 12 for stage 2, 19 for stage 3, 26 for stage 4). It is written from the
written requirements only and is run against each accepted stage folder after the run.

Only this digest is published before the judged run. The four files are published after the
event closes, so anyone can confirm they are the same bytes that were sealed here:

```
python factory/tools/seal_holdout.py verify <folder with the four published files> \
  379f28f6c49b9b995f8d6a5fff58e6e8612377693104ccdf759c5f5f04abc9a9
```

The digest covers each file's name and exact bytes, length-prefixed, in sorted order
(`factory/tools/seal_holdout.py`). Files: 4. Sealed 2026-09-29, before the judged dispatch.
