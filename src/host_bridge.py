"""Authenticated transport adapter; Ollama and Open WebUI own model/UI logic."""
import argparse
import hmac
import http.client
import json
import logging
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
INFERENCE_PATHS = {"/api/chat", "/api/generate", "/api/embed", "/api/embeddings", "/v1/chat/completions", "/v1/completions", "/v1/embeddings", "/v1/responses"}
ALLOWED = {
    "GET": {"/api/tags", "/api/ps", "/api/version", "/v1/models", "/bridge/status", "/healthz"},
    "POST": INFERENCE_PATHS | {"/api/show", "/api/pull", "/api/create", "/api/copy"},
    "DELETE": {"/api/delete"},
}


def read_env(path):
    values = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep: raise ValueError("Invalid environment line")
            values[key.strip()] = value.strip().strip('"')
    return values


def download_status(directory):
    path = Path(directory)
    manifest = path / "download-manifest.json"
    if not manifest.exists(): return {"available": False}
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    files = []
    for entry in metadata["files"]:
        name = entry["rfilename"]
        if Path(name).name != name or "/" in name or "\\" in name or ".." in name: continue
        complete = (path / name).exists()
        p = path / name if complete else path / (name + ".part")
        size = p.stat().st_size if p.exists() else 0
        files.append({"name": name, "downloaded": min(size, entry["size"]), "total": entry["size"], "complete": complete and size == entry["size"]})
    total = sum(f["total"] for f in files)
    downloaded = sum(f["downloaded"] for f in files)
    return {"available": True, "repository": metadata["repository"], "total": total, "downloaded": downloaded, "percent": round(downloaded / total * 100, 2) if total else 0, "complete": all(f["complete"] for f in files), "files": files}


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def handler_factory(token, upstream, model_dir, cloud_ip=None, inference_limit=1, timeout=600, max_pending=4, queue_timeout=120):
    parsed = urlsplit(upstream)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.path not in {"", "/"}:
        raise ValueError("Ollama upstream must be a loopback HTTP address")
    if len(token) < 32: raise ValueError("BRIDGE_TOKEN must contain at least 32 characters")
    if inference_limit < 1 or max_pending < 0 or queue_timeout < 0: raise ValueError("Invalid inference queue configuration")
    slots = threading.BoundedSemaphore(inference_limit)
    admissions = threading.BoundedSemaphore(inference_limit + max_pending)
    counts = {"active": 0, "queued": 0, "total": 0, "failed": 0}
    lock = threading.Lock()
    started = time.monotonic()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "LeoModelBridge/1.0"

        def log_message(self, fmt, *args):
            logging.info("%s %s", self.client_address[0], fmt % args)

        def send_json(self, status, data):
            raw = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            if self.close_connection: self.send_header("Connection", "close")
            if status == 429: self.send_header("Retry-After", "10")
            self.end_headers()
            self.wfile.write(raw)

        def reject(self, status, message, code):
            self.close_connection = True
            self.send_json(status, {"error": {"message": message, "type": "bridge_error", "code": code}})

        def do_GET(self): self.dispatch()
        def do_POST(self): self.dispatch()
        def do_DELETE(self): self.dispatch()
        def do_HEAD(self): self.reject(405, "Method not allowed", "method_not_allowed")
        def do_OPTIONS(self): self.reject(405, "Method not allowed", "method_not_allowed")

        def dispatch(self):
            self.connection.settimeout(30)
            request_id = str(uuid.uuid4())
            path = urlsplit(self.path).path
            if self.path != path or path not in ALLOWED.get(self.command, set()):
                self.reject(404, "Route not available", "route_not_found"); return
            if cloud_ip and self.client_address[0] not in {cloud_ip, "127.0.0.1", "::1"}:
                self.reject(403, "Source host not permitted", "source_forbidden"); return
            expected = "Bearer " + token
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), expected.encode()):
                self.reject(401, "A valid bridge credential is required", "unauthorized"); return
            if self.headers.get("Transfer-Encoding"):
                self.reject(400, "Transfer-Encoding requests are not supported", "invalid_request"); return
            payload = None
            if self.command in {"POST", "DELETE"}:
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if not 0 < size <= 8 * 1024 * 1024:
                        self.reject(413, "Request body must be between 1 byte and 8 MB", "body_too_large"); return
                    payload = self.rfile.read(size)
                    if len(payload) != size: raise ValueError("Incomplete body")
                    data = json.loads(payload)
                    if not isinstance(data, dict): raise ValueError("Object required")
                except (ValueError, TimeoutError):
                    self.reject(400, "Invalid JSON request", "invalid_request"); return
            if path == "/healthz":
                self.send_json(200, {"status": "ok"}); return
            if path == "/bridge/status":
                with lock: snapshot = dict(counts)
                self.send_json(200, {"service": "leo-model-bridge", "uptime_seconds": int(time.monotonic() - started), "requests": snapshot, "download": download_status(model_dir)}); return
            inference = path in INFERENCE_PATHS
            if inference:
                if not admissions.acquire(blocking=False):
                    self.reject(429, "GPU request queue is full; retry later", "model_busy"); return
                with lock: counts["queued"] += 1
                acquired = slots.acquire(timeout=queue_timeout)
                with lock: counts["queued"] -= 1
                if not acquired:
                    admissions.release()
                    self.reject(429, "GPU queue wait timed out; retry later", "model_busy"); return
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 11434, timeout=timeout)
            headers_sent = False
            if inference:
                with lock:
                    counts["active"] += 1
                    counts["total"] += 1
            try:
                conn.request(self.command, path, body=payload, headers={"Content-Type": "application/json"})
                upstream_response = conn.getresponse()
                self.send_response(upstream_response.status)
                self.send_header("Content-Type", upstream_response.getheader("Content-Type", "application/json"))
                self.send_header("Transfer-Encoding", "chunked")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Accel-Buffering", "no")
                self.send_header("X-Request-Id", request_id)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                headers_sent = True
                if upstream_response.status >= 400 and inference:
                    with lock: counts["failed"] += 1
                while chunk := upstream_response.read1(16384):
                    self.wfile.write(f"{len(chunk):X}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                self.wfile.flush()
            except (OSError, http.client.HTTPException) as error:
                if inference:
                    with lock: counts["failed"] += 1
                logging.warning("Upstream failure request_id=%s type=%s", request_id, type(error).__name__)
                if not headers_sent: self.reject(503, "Model host is not ready", "upstream_unavailable")
                self.close_connection = True
            finally:
                conn.close()
                if inference:
                    with lock: counts["active"] -= 1
                    slots.release()
                    admissions.release()
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=str(ROOT / ".env"))
    args = parser.parse_args()
    env = {**read_env(args.env), **os.environ}
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if os.name == "nt":
        # Keep this model host awake while running; does not change system power settings.
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    model_dir = (ROOT / env.get("MODEL_DIRECTORY", "../models/gpt-oss-20b")).resolve()
    handler = handler_factory(env["BRIDGE_TOKEN"], env.get("OLLAMA_URL", "http://127.0.0.1:11434"), model_dir, env.get("CLOUD_TAILSCALE_IP"), int(env.get("MAX_CONCURRENT", "1")), max_pending=int(env.get("MAX_PENDING", "4")), queue_timeout=float(env.get("QUEUE_TIMEOUT", "120")))
    hosts = {env.get("EDGE_BIND", "127.0.0.1"), "127.0.0.1"}
    servers = []
    for host in hosts:
        server = BridgeServer((host, int(env.get("EDGE_PORT", "8787"))), handler)
        servers.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        logging.info("Bridge listening at %s:%s", host, server.server_port)
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        for server in servers: server.shutdown()


if __name__ == "__main__": main()
