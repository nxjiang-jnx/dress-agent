#!/usr/bin/env python3
"""Run render/bake jobs on one GPU. Jobs are shared by N workers through a lock
directory, so two workers (GPU 2 and 3) drain one queue without overlap.

    python run_jobs.py jobs.json --gpu 2 &
    python run_jobs.py jobs.json --gpu 3 &

A job: {"id": str, "kind": "orbit"|"bake", "out": dir, "args": [...]}.
Done = out/orbit.json or out/bake.json exists.
"""
import argparse
import json
import os
import subprocess
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
DA = Path("/home/nanxiangjiang/agentic_garment/DressAnything")
SCRIPT = {"orbit": TOOLS / "orbit_render.py", "bake": TOOLS / "bake_case.py",
          "bodyin": TOOLS / "bake_case.py"}
MARK = {"orbit": "orbit.json", "bake": "bake.json", "bodyin": "body_inner.done"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("jobs", type=Path)
    p.add_argument("--gpu", required=True)
    a = p.parse_args()
    jobs = json.loads(a.jobs.read_text())
    locks = a.jobs.with_suffix(".locks")
    locks.mkdir(exist_ok=True)
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=a.gpu,
               GARMENT_PYTHON="/data/nanxiangjiang/miniconda3/envs/garment/bin/python")
    for job in jobs:
        out = Path(job["out"])
        if (out / MARK[job["kind"]]).is_file():
            continue
        try:
            (locks / job["id"].replace("/", "__")).mkdir()
        except FileExistsError:
            continue
        out.mkdir(parents=True, exist_ok=True)
        cmd = ["blender", "--background", "--python", str(SCRIPT[job["kind"]]), "--",
               "--out-dir", str(out)] + [str(x) for x in job["args"]]
        t = time.time()
        with open(out / "job.log", "w") as log:
            log.write(" ".join(cmd) + "\n")
            log.flush()
            r = subprocess.run(cmd, cwd=DA, env=env, stdout=log, stderr=subprocess.STDOUT)
        ok = (out / MARK[job["kind"]]).is_file()
        if not ok:   # free the lock so a later pass can retry
            (locks / job["id"].replace("/", "__")).rmdir()
        print(f"[gpu{a.gpu}] {job['id']} {'ok' if ok else 'FAIL'} rc={r.returncode} {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
