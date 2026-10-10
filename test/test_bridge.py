import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from host_bridge import BridgeServer, handler_factory, download_status

TOKEN = "a-test-only-token-" + "x" * 40

class FakeOllama(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    began = threading.Event()
    release = threading.Event()

    def log_message(self, *_): pass
    def do_GET(self):
        raw = json.dumps({"models": [{"name": "test:latest"}]}).encode()
        self.send_response(200); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        first = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
        self.wfile.write(f"{len(first):X}\r\n".encode() + first + b"\r\n"); self.wfile.flush()
        self.began.set()
        if value.get("hold"): self.release.wait(3)
        last = b'data: [DONE]\n\n'
        try:
            self.wfile.write(f"{len(last):X}\r\n".encode() + last + b"\r\n0\r\n\r\n"); self.wfile.flush()
        except OSError: pass

class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
        cls.bridge = BridgeServer(("127.0.0.1", 0), handler_factory(TOKEN, f"http://127.0.0.1:{cls.upstream.server_port}", cls.tmp.name, max_pending=0))
        for server in [cls.upstream, cls.bridge]: threading.Thread(target=server.serve_forever, daemon=True).start()
    @classmethod
    def tearDownClass(cls):
        for server in [cls.bridge, cls.upstream]: server.shutdown(); server.server_close()
        cls.tmp.cleanup()
    def request(self, path, method="GET", data=None, token=TOKEN):
        conn = http.client.HTTPConnection("127.0.0.1", self.bridge.server_port, timeout=5)
        headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
        conn.request(method, path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse(); raw = response.read(); status = response.status; conn.close()
        return status, raw
    def test_authentication_blocks_missing_or_wrong_token(self):
        for token in ["", "incorrect"]:
            status, _ = self.request("/api/tags", token=token)
            self.assertEqual(status, 401)
    def test_authenticated_model_list(self):
        status, raw = self.request("/api/tags")
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw)["models"][0]["name"], "test:latest")
    def test_non_allowlisted_routes_and_queries(self):
        for path in ["/api/blobs/sha256:anything", "/api/push", "/api/tags?url=http://evil.invalid", "/../../etc/passwd"]:
            status, _ = self.request(path)
            self.assertEqual(status, 404)
    def test_stream_is_flushed_before_completion_and_concurrency_is_bounded(self):
        FakeOllama.began.clear(); FakeOllama.release.clear()
        conn = http.client.HTTPConnection("127.0.0.1", self.bridge.server_port, timeout=5)
        conn.request("POST", "/v1/chat/completions", json.dumps({"hold": True}), {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        start = time.monotonic(); chunk = res.read1(4096)
        self.assertIn(b"hello", chunk); self.assertLess(time.monotonic() - start, 1)
        status, _ = self.request("/v1/chat/completions", "POST", {})
        self.assertEqual(status, 429)
        FakeOllama.release.set(); rest = res.read(); conn.close()
        self.assertIn(b"[DONE]", rest)
        status, _ = self.request("/v1/chat/completions", "POST", {})
        self.assertEqual(status, 200)
    def test_invalid_json_is_not_forwarded(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.bridge.server_port, timeout=5)
        conn.request("POST", "/api/chat", "not json", {"Authorization": "Bearer " + TOKEN})
        res = conn.getresponse(); self.assertEqual(res.status, 400); res.read(); conn.close()
    def test_overlapping_requests_wait_without_overloading_gpu_and_queue_is_bounded(self):
        server = BridgeServer(("127.0.0.1", 0), handler_factory(TOKEN, f"http://127.0.0.1:{self.upstream.server_port}", self.tmp.name, max_pending=1, queue_timeout=2))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        previous = self.bridge
        self.bridge = server
        FakeOllama.began.clear(); FakeOllama.release.clear()
        first = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        first.request("POST", "/api/chat", json.dumps({"hold": True}), {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        response = first.getresponse(); response.read1(4096)
        result = []
        waiting = threading.Thread(target=lambda: result.append(self.request("/api/chat", "POST", {})))
        waiting.start()
        try:
            deadline = time.monotonic() + 1
            while time.monotonic() < deadline:
                _, raw = self.request("/bridge/status")
                counts = json.loads(raw)["requests"]
                if counts["queued"] == 1: break
                time.sleep(0.01)
            self.assertEqual(counts["queued"], 1)
            self.assertEqual(counts["active"], 1)
            self.assertEqual(result, [])
            self.assertEqual(self.request("/api/chat", "POST", {})[0], 429)
            FakeOllama.release.set(); response.read(); first.close()
            waiting.join(3)
            self.assertEqual(result[0][0], 200)
            self.assertIn(b"[DONE]", result[0][1])
            _, raw = self.request("/bridge/status")
            self.assertEqual(json.loads(raw)["requests"]["queued"], 0)
            self.assertEqual(self.request("/api/chat", "POST", {})[0], 200)
        finally:
            FakeOllama.release.set(); first.close(); waiting.join(3)
            self.bridge = previous
            server.shutdown(); server.server_close()
    def test_download_status_distinguishes_part_files(self):
        directory = Path(self.tmp.name)
        (directory / "download-manifest.json").write_text(json.dumps({"repository": "fixture", "files": [{"rfilename": "model.safetensors", "size": 8}]}))
        (directory / "model.safetensors.part").write_bytes(b"1234")
        result = download_status(directory)
        self.assertEqual(result["percent"], 50); self.assertFalse(result["complete"])
        (directory / "model.safetensors").write_bytes(b"12345678")
        self.assertTrue(download_status(directory)["complete"])
    def test_remote_upstream_and_weak_token_are_rejected(self):
        with self.assertRaises(ValueError): handler_factory(TOKEN, "http://untrusted.invalid", self.tmp.name)
        with self.assertRaises(ValueError): handler_factory("short", "http://127.0.0.1:11434", self.tmp.name)

if __name__ == "__main__": unittest.main()
