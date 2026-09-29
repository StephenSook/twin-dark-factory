You are @stephensookra/solo. Build stage 1 of the task below, alone. This message is the only input
you will get from me. Do not ask me anything or wait for me at any point; resolve every question
from the written requirements.

Paths:
- Requirements: /home/ubuntu/work/dark-factory-wearedevs/pocketful/spec/stage-1.md
- Provided checks: /home/ubuntu/work/dark-factory-wearedevs/pocketful/test/ (run them only through the check tool below)
- Result repository: /home/ubuntu/work/band-work/current
- Stage folder: /home/ubuntu/work/band-work/current/stage-1/

Folder rules:
- The stage folder is a complete service with its source, a Dockerfile and a RUN.md.
- Nothing is committed outside the stage folder. Never write README.md or FACTORY.md.

Commits:
- Commit your own work under your own name:
  git -c user.name=solo -c user.email=solo@band.local commit -m "<what and why>"
- The repository refuses commits with any other author or outside stage folders. Never
  bypass that check and never rewrite history.

Check tool (from /home/ubuntu/work/dark-factory-wearedevs, with its virtual environment active):
  /home/ubuntu/work/dark-factory-wearedevs/.venv/bin/python -m harness run --track pocketful --repo /home/ubuntu/work/band-work/current --stage 1 --mode isolated --out /home/ubuntu/work/band-work/checks/baseline-solo/s1-<attempt>
It runs the stage 1 suite and then the next suite, which must fail. The provided checks are only
a part of the checks used for grading; build from the written requirements, not from the checks.

When stage 1 is done, post your report and stop.
