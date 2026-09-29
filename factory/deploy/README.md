# Live demo

The public demo runs the band's last stage folder, built unchanged from its own Dockerfile, behind
a small front door (`proxy.py`, standard library only):

- `/_test/*` answers 404. The spec leaves reset, export and import unauthenticated, which is right
  for a test harness and wrong for a public URL.
- Each client address is rate limited (120 requests per 10 seconds) and bodies are capped at 1 MiB.
- Every hour the front door reseeds the service from `seed.json` through the service's own reset
  endpoint, so the demo accounts always work. `/__demo/status` shows the last reseed.
- Responses are passed through unchanged, including the service's own security headers.

Demo logins (all use the password `pocketful demo`): `ada@demo.example`, `bob@demo.example`,
`cleo@demo.example`, `dev@demo.example`. Anyone can also sign up; the hourly reseed clears it.

Build and run locally:

```
docker build -t app stage-4
docker build -t demo --build-arg APP_IMAGE=app --build-arg APP_CMD="<the CMD from stage-4/Dockerfile>" deploy
docker run --rm -p 10000:10000 demo
```

The `demo-image` workflow does the same in CI, smoke tests it, and publishes the image to the GitHub
container registry for the host to pull.
