#!/usr/bin/env python3
"""Batch form of DressAnything render/composite_tone_passes.py (--rgba):
Standard garment pixels over the AgX pass, alpha from the AgX pass."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image


def one(job):
    agx, std, mask, out = job
    a = Image.open(agx).convert("RGBA")
    s = Image.open(std).convert("RGBA")
    m = Image.open(mask).convert("L")
    r = Image.composite(s, a, m)
    r.putalpha(a.getchannel("A"))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    r.save(out)


if __name__ == "__main__":
    jobs = json.loads(Path(sys.argv[1]).read_text())
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, jobs))
    print(f"composited {len(jobs)}")
