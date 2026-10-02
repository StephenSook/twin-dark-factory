#!/usr/bin/env python3
"""Regression checks for lossless demo startup and untrusted forwarding headers."""
import base64
import importlib.util
import json
import pathlib
import re
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


# Behaviour on one keep-alive connection, the way the host's edge reuses upstream sockets.
import http.server
import socket
import threading


class FakeService(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        data = json.dumps({"service": self.path}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = answer


def serve(handler):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


service, front = serve(FakeService), serve(proxy.Handler)
proxy.UP_PORT = service.server_address[1]


def exchange(raw):
    """Send raw bytes on one connection and return everything the proxy writes before closing."""
    with socket.create_connection(front.server_address, timeout=10) as sock:
        sock.sendall(raw)
        chunks = []
        try:
            while chunk := sock.recv(65536):
                chunks.append(chunk)
        except socket.timeout:
            pass
    return b"".join(chunks)


def statuses(data):
    # A pipelined response starts right after the previous body, with no line break before it.
    return re.findall(rb"HTTP/1\.1 (\d{3}) ", data)


smuggled = b"GET /me HTTP/1.1\r\nHost: demo\r\n\r\n"
for label, first in (
    ("a refused test endpoint", b"POST /_test/reset HTTP/1.1\r\nHost: demo\r\nContent-Length: 2\r\n\r\n{}"),
    ("a refused test endpoint whose body is a whole request",
     b"POST /_test/reset HTTP/1.1\r\nHost: demo\r\nContent-Length: %d\r\n\r\n" % len(smuggled) + smuggled),
    ("the status endpoint", b"POST /__demo/status HTTP/1.1\r\nHost: demo\r\nContent-Length: 2\r\n\r\n{}"),
    ("a chunked body", b"POST /me HTTP/1.1\r\nHost: demo\r\nTransfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n"),
    ("two Content-Length headers",
     b"POST /me HTTP/1.1\r\nHost: demo\r\nContent-Length: 2\r\nContent-Length: 0\r\n\r\n{}"),
    ("a malformed header line the stdlib stops parsing at",
     b"POST /me HTTP/1.1\r\nHost: demo\r\nContent-Length : %d\r\n\r\n" % len(smuggled) + smuggled),
    ("a nested-encoded backslash route to the test endpoints",
     b"GET /_test%255Creset HTTP/1.1\r\nHost: demo\r\n\r\n"),
    ("an empty Transfer-Encoding field hiding a chunked one",
     b"POST /me HTTP/1.1\r\nHost: demo\r\nTransfer-Encoding:\r\nTransfer-Encoding: chunked\r\nContent-Length: 4\r\n\r\n"
     b"20\r\n" + smuggled + b"\r\n0\r\n\r\n"),
    ("a Content-Length of non-ASCII digits",
     b"POST /me HTTP/1.1\r\nHost: demo\r\nContent-Length: \xb2\r\n\r\nx"),
    ("a Content-Length too long to convert",
     b"POST /me HTTP/1.1\r\nHost: demo\r\nContent-Length: " + b"9" * 5000 + b"\r\n\r\n"),
):
    data = exchange(first + b"GET /health HTTP/1.1\r\nHost: demo\r\n\r\n")
    codes = statuses(data)
    check(f"{label}: the proxy answers once and closes, so no leftover bytes become a request",
          len(codes) == 1 and codes[0] != b"501" and b"Connection: close" in data and b'"service"' not in data)

data = exchange(b"POST /me HTTP/1.1\r\nHost: demo\r\nContent-Length: 2\r\n\r\n{}"
                b"GET /health HTTP/1.1\r\nHost: demo\r\nConnection: close\r\n\r\n")
check("a forwarded request keeps its connection and the next request reaches the service intact",
      statuses(data) == [b"200", b"200"] and b'{"service": "/me"}' in data and b'{"service": "/health"}' in data)
service.shutdown()
front.shutdown()

print(f"failures: {len(failures)}")
sys.exit(1 if failures else 0)
