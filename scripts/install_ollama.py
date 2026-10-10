"""Extract the upstream portable release using remotezip, preserving GPU choice.

Vulkan is a small initial GPU runtime. Full CUDA installation can be extracted
from the complete upstream ZIP later without changing model/configuration data.
"""
import argparse
import concurrent.futures
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".runtime" / "python"))
import requests
from remotezip import RemoteZip, RemoteFetcher

VERSION = "v0.35.1"
URL = f"https://github.com/ollama/ollama/releases/download/{VERSION}/ollama-windows-amd64.zip"
SIZE = 1471094402

class ReleaseFetcher(RemoteFetcher):
    def get_file_size(self):
        # Official GitHub release metadata; signed asset URLs reject suffix ranges.
        return SIZE

def remote_archive(session):
    return RemoteZip(URL, session=session, fetcher=ReleaseFetcher, support_suffix_range=False, timeout=90)


def install(backend, proxy):
    destination = ROOT / ".runtime" / "ollama"
    destination.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    if proxy: session.proxies = {"https": proxy, "http": proxy}
    with remote_archive(session) as archive:
        names = [item.filename for item in archive.infolist() if not item.is_dir() and (
            item.filename == "ollama.exe" or item.filename.count("/") == 2 or
            item.filename.startswith(f"lib/ollama/{backend}/"))]
    def extract(name):
        for attempt in range(8):
            try:
                s = requests.Session()
                if proxy: s.proxies = {"https": proxy, "http": proxy}
                with remote_archive(s) as archive:
                    info = archive.getinfo(name)
                    target = destination / name
                    if target.exists() and target.stat().st_size == info.file_size:
                        return
                    archive.extract(name, destination)
                    print("EXTRACTED", name, info.file_size, flush=True)
                return
            except Exception as error:
                print("RETRY", name, type(error).__name__, flush=True)
                time.sleep(min(2 * (attempt + 1), 10))
        raise RuntimeError("Extraction failed: " + name)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(extract, names))
    (destination / "installation.json").write_text(json.dumps({"version": VERSION, "backend": backend, "source": URL}, indent=2))
    print("OLLAMA_READY", destination, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["vulkan", "cuda_v12", "cuda_v13"], default="vulkan")
    parser.add_argument("--proxy", default="http://127.0.0.1:7897")
    args = parser.parse_args()
    install(args.backend, args.proxy)
