"""Run real public-site Chromium acceptance on leo-ubuntu; keep secrets private."""
import json
import argparse
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
HOST = "ubuntu@100.73.83.110"
REMOTE = "/home/ubuntu/leo-project/model-bridge"
IMAGE = "leo-model-browser-test:1.63.0"


def ssh(command, **kwargs):
    return subprocess.run(["ssh", HOST, command], check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='https://d.58nft.net')
    args = parser.parse_args()
    base = args.base.rstrip('/')
    parsed = urlsplit(base)
    assert parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment and parsed.path in ('', '/'), 'Use a public HTTPS origin'
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run_id = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    remote_out = REMOTE + "/artifacts/browser/" + run_id
    private_file = REMOTE + "/artifacts/browser-credentials-" + run_id + ".json"
    local_out = ROOT / "artifacts" / "browser" / run_id
    local_out.mkdir(parents=True)
    credentials = json.loads((ROOT / "data" / "credentials.json").read_text(encoding="utf-8"))
    private = {key: credentials[key] for key in ("admin_password", "client_email", "client_password")}
    ssh("umask 077; mkdir -p " + shlex.quote(remote_out) + " " + shlex.quote(REMOTE + "/test/browser"))
    subprocess.run(["scp", str(ROOT / "test/browser/Dockerfile"), str(ROOT / "test/browser/e2e.py"),
                    HOST + ":" + REMOTE + "/test/browser/"], check=True)
    ssh("sudo docker image inspect " + IMAGE + " >/dev/null 2>&1 || sudo docker build -t " + IMAGE
        + " " + REMOTE + "/test/browser", timeout=900)
    exit_code = 1
    try:
        ssh("umask 077; cat > " + shlex.quote(private_file), input=json.dumps(private).encode())
        command = ("sudo docker run --rm --init --memory=700m --shm-size=256m --cpus=1.0 "
                   "-e " + shlex.quote('MODEL_TEST_BASE=' + base) + " "
                   "-v " + REMOTE + "/test/browser:/tests:ro "
                   "-v " + remote_out + ":/artifacts "
                   "-v " + private_file + ":/run/browser-credentials.json:ro "
                   + IMAGE + " python -u e2e.py")
        completed = subprocess.run(["ssh", HOST, command], timeout=900)
        exit_code = completed.returncode
    finally:
        # Delete only this run's temporary credential file, including on failure.
        ssh("rm -f -- " + shlex.quote(private_file))
        subprocess.run(["scp", "-r", HOST + ":" + remote_out + "/.", str(local_out)], check=True)
    print("Browser report and screenshots: " + str(local_out))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
