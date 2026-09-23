#!/usr/bin/env python3
"""Clean baked textures: keep texels well inside the UV triangles, refill the
rest (island borders, gutters, holes) from the nearest kept texel."""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def coverage(tris, w, h):
    m = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(m)
    for t in tris:
        d.polygon([(u * w, (1.0 - v) * h) for u, v in t], fill=255)
    return np.asarray(m) > 0


def fill(tex_path, tris):
    im = np.asarray(Image.open(tex_path).convert("RGB"))
    h, w = im.shape[:2]
    mask = coverage(tris, w, h)
    # the outer two texels of every island see the neighbouring panel at grazing
    # distance and bake too dark; take them from the interior instead
    core = ndimage.binary_erosion(mask, iterations=2)
    # tiny islands the erosion wiped out keep all their texels
    keep = core | (mask & ~ndimage.binary_dilation(core, iterations=3))
    _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
    Image.fromarray(im[iy, ix]).save(tex_path)


def main(out):
    out = Path(out)
    meta = json.loads((out / "bake.json").read_text())
    for m in meta["meshes"]:
        tris = np.load(out / f"{m['name']}.uv.npy")
        for key in ("tex", "tex_back"):
            if m.get(key):
                fill(out / m[key], tris)
        print("seam fill", m["name"])


if __name__ == "__main__":
    main(sys.argv[1])
