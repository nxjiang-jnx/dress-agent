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


def fill(tex_path, tris, lit_source=False):
    im = np.asarray(Image.open(tex_path).convert("RGB"))
    h, w = im.shape[:2]
    mask = coverage(tris, w, h)
    # the outer two texels of every island see the neighbouring panel at grazing
    # distance and bake too dark; take them from the interior instead
    core = ndimage.binary_erosion(mask, iterations=2)
    # tiny islands the erosion wiped out keep all their texels
    keep = core | (mask & ~ndimage.binary_dilation(core, iterations=3))
    hidden = Path(tex_path).with_suffix(".hidden.npy")
    if hidden.is_file():
        # cloth inside the body (under a poke, from hidden_masks.py) bakes black;
        # refill it from visible cloth so the poke keeps a clean edge
        hid = np.load(hidden)
        if hid.shape == (h, w):
            # the few visible texels next to the contact are darkened by it too (in Cycles that
            # is a sub-pixel line), so they are refilled as well, from farther out: ~2.5 mm
            band = max(2, round(6 * w / 4096))
            keep &= ~ndimage.binary_dilation(hid, iterations=band)
            if lit_source:
                # skin has one albedo, so brightness is lighting: never refill a poke from
                # skin in the shadow of a sleeve or waistband
                lum = im.astype(np.float32).mean(axis=2)
                keep &= lum >= 0.55 * np.percentile(lum[mask], 90)
    _, (iy, ix) = ndimage.distance_transform_edt(~keep, return_indices=True)
    Image.fromarray(im[iy, ix]).save(tex_path)


# SMPL-X UV boxes (u0, u1, v0, v1 as image fractions, v from the top) holding the eye sockets:
# faces that curl into the head behind the eyeball. They bake black, and mipmaps bleed that
# black into the eyelid rim, while Cycles shows only a soft crease there.
EYE_BOXES = [(0.2393, 0.2673, 0.1904, 0.2129), (0.3374, 0.3650, 0.1904, 0.2129)]


def fix_eyes(tex_path, crease=0.82):
    im = np.asarray(Image.open(tex_path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    for u0, u1, v0, v1 in EYE_BOXES:
        ys, xs = slice(int(v0 * h), int(v1 * h)), slice(int(u0 * w), int(u1 * w))
        box = im[ys, xs]
        lum = box.mean(axis=2)
        p90 = np.percentile(lum, 90)
        dark = lum < 0.8 * p90
        if not dark.any() or dark.all():
            continue
        skin = np.median(box[lum >= np.percentile(lum, 75)], axis=0)
        # soft ring: the socket takes a darkened skin tone, feathered into the rim
        dark = ndimage.binary_dilation(dark, iterations=1)
        box[dark] = skin * crease
        im[ys, xs] = box
    Image.fromarray(np.clip(im + 0.5, 0, 255).astype(np.uint8)).save(tex_path)


SMPLX_UV = Path("/data/nanxiangjiang/baselines/PEAR/assets/SMPLX/smplx_uv.obj")


def eyeball_tris():
    """UV triangles of the two SMPL-X eyeballs (the mesh's small connected components)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    vts, f, ft = [], [], []
    for line in SMPLX_UV.read_text().splitlines():
        if line.startswith("vt "):
            vts.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("f "):
            c = [x.split("/") for x in line.split()[1:]]
            f.append([int(a[0]) - 1 for a in c])
            ft.append([int(a[1]) - 1 for a in c])
    f, ft, vts = np.array(f), np.array(ft), np.array(vts)
    n = f.max() + 1
    r = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    c = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    _, lab = connected_components(coo_matrix((np.ones(len(r)), (r, c)), shape=(n, n)), directed=False)
    main_part = np.bincount(lab).argmax()
    return [vts[ft[lab[f[:, 0]] == k]] for k in np.unique(lab) if k != main_part]


def fix_eyeballs(tex_path):
    """Eyeball texels hidden behind the lids bake dark and mip into the visible part,
    drawing a dark ring the Cycles render does not have. Give them the lit eyeball tone."""
    im = np.asarray(Image.open(tex_path).convert("RGB")).astype(np.float32)
    h, w = im.shape[:2]
    for tris in eyeball_tris():
        mask = coverage(tris, w, h)
        mask = ndimage.binary_dilation(mask, iterations=3)
        lum = im[mask].mean(axis=1)
        lit = lum >= 0.8 * np.percentile(lum, 95)
        tone = np.median(im[mask][lit], axis=0)
        vals = im[mask]
        vals[~lit] = tone
        im[mask] = vals
    Image.fromarray(np.clip(im + 0.5, 0, 255).astype(np.uint8)).save(tex_path)


def main(out):
    out = Path(out)
    meta = json.loads((out / "bake.json").read_text())
    for m in meta["meshes"]:
        tris = np.load(out / f"{m['name']}.uv.npy")
        for key in ("tex", "tex_back"):
            if m.get(key):
                fill(out / m[key], tris, lit_source=(m["name"] == "body" and key == "tex"))
        if m["name"] == "body" and m.get("uv") == "bake":
            fix_eyes(out / m["tex"])
            fix_eyeballs(out / m["tex"])
        print("seam fill", m["name"])


if __name__ == "__main__":
    main(sys.argv[1])
