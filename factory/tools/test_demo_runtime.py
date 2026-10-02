#!/usr/bin/env python3
"""Regression checks for lossless demo startup and untrusted forwarding headers."""
import base64
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROXY_PATH = ROOT / "factory" / "deploy" / "proxy.py"
WORKFLOW = ROOT / "factory" / "result-ci" / "demo-image.yml"
DOCKERFILE = ROOT / "factory" / "deploy" / "Dockerfile"

spec = importlib.util.spec_from_file_location("demo_proxy", PROXY_PATH)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)
failures = []


def check(label, condition):
    print(("ok   " if condition else "BAD  ") + label)
    if not condition:
        failures.append(label)


argv = ["sh", "-c", "printf 'HELLO WORLD\\n'; printf \"$SAFE\""]
encoded = base64.b64encode(json.dumps(argv, separators=(",", ":")).encode()).decode()
check("image argv survives spaces, quotes and shell metacharacters", proxy.decode_app_argv(encoded) == argv)

for label, raw in (
    ("invalid base64 is refused", "not base64!"),
    ("an empty argv is refused", base64.b64encode(b"[]").decode()),
    ("a non-string argv item is refused", base64.b64encode(b'["ok",3]').decode()),
):
    try:
        proxy.decode_app_argv(raw)
    except ValueError:
        check(label, True)
    else:
        check(label, False)

workflow = WORKFLOW.read_text()
check("workflow reads the built image configuration", "docker image inspect app" in workflow)
check("workflow does not send image argv through GITHUB_OUTPUT", "GITHUB_OUTPUT" not in workflow)
check("workflow passes only base64 argv into the build shell", '--build-arg APP_ARGV_B64="$app_argv_b64"' in workflow)

dockerfile = DOCKERFILE.read_text()
check("wrapper replaces an inherited image entrypoint with its own runtime", 'ENTRYPOINT ["/opt/demo-python/bin/python3", "/demo/proxy.py"]' in dockerfile)
check("front-door runtime is pinned by checksum", "PBS_SHA256=269b2c99e4db15b242bf01832f4fea1e8f1a664f273cff519393f296e9820b41" in dockerfile and "checksum mismatch" in dockerfile)
check("wrapper clears an inherited image command", "CMD []" in dockerfile)

proxy_text = PROXY_PATH.read_text()
check("rate limiting ignores caller-controlled forwarding headers", 'self.headers.get("X-Forwarded-For")' not in proxy_text)
check("status requests are rate limited too", proxy_text.index("if not allowed(ip)") < proxy_text.index('if self.path == "/__demo/status"'))

print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
