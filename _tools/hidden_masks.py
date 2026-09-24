#!/usr/bin/env python3
"""Mark cloth texels that lie inside the body.

Where the body pokes through snug cloth, the patch of cloth under the poke sits inside the body:
it is never seen and bakes black. Texture filtering then bleeds that black around every poke as a
dark ring, which Cycles, intersecting per pixel, never shows. The pokes are smaller than the cloth
triangles, so the test runs per texel: each texel of a garment's baked textures is mapped back to
its 3D point and checked against the body with its winding number: cloth lying on the skin sits
within a millimetre of it, where the sign against the nearest face flips from texel to texel and
would mark large visible areas as hidden. Writes <texture>.hidden.npy (True = inside), which
seam_fill.py refills from visible cloth.

    blender --background --python hidden_masks.py -- --input garment_final_pose.glb \
        --layers L0 --out-dir bake/<case>/s0
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

RENDER = Path("/home/nanxiangjiang/agentic_garment/DressAnything/render")
_spec = importlib.util.spec_from_file_location("da_render", RENDER / "blender_render.py")
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)
NEAR = 0.02    # only cloth within 2 cm of the body can dip inside it
COVER = 0.005  # skin with cloth lying within 5 mm above it is never seen
_bspec = importlib.util.spec_from_file_location("bake_case", Path(__file__).resolve().parent / "bake_case.py")
bake_case = importlib.util.module_from_spec(_bspec)
_bspec.loader.exec_module(bake_case)


def world(obj, normals=False):
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get("co", co)
    m = np.asarray(obj.matrix_world, np.float64)
    me.calc_loop_triangles()
    co = co.reshape(n, 3) @ m[:3, :3].T + m[:3, 3]
    if not normals:
        return co
    nr = np.empty(n * 3, np.float64)
    me.vertices.foreach_get("normal", nr)
    nr = nr.reshape(n, 3) @ m[:3, :3].T
    return co, nr / (np.linalg.norm(nr, axis=1, keepdims=True) + 1e-12)


def inside(points, bv, bf):
    """Winding number > 1/2 against the body, computed by igl in the garment Python."""
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp) / "q.npz", Path(tmp) / "w.npy"
        np.savez(src, V=bv, F=bf, Q=points)
        subprocess.run([bake_case.nt.compositor_python(), str(Path(__file__).resolve().parent / "winding.py"),
                        str(src), str(dst)], check=True)
        return np.load(dst) > 0.5


def texel_points(obj, co, size, candidates, uv_name=None, attr=None):
    """Pixel coords and 3D points (and interpolated attr) of the texels of the candidate triangles."""
    me = obj.data
    uv = (me.uv_layers[uv_name] if uv_name else me.uv_layers[0]).data
    w = h = size
    ys_all, xs_all, pts_all, att_all = [], [], [], []
    for t in candidates:
        lt = me.loop_triangles[t]
        px = np.array([[uv[l].uv[0] * w, (1.0 - uv[l].uv[1]) * h] for l in lt.loops])
        P = co[list(lt.vertices)]
        x0, y0 = np.floor(px.min(0)).astype(int)
        x1, y1 = np.ceil(px.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, w - 1), min(y1, h - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        q = np.stack([xs.ravel() + 0.5, ys.ravel() + 0.5], 1)
        a, b, c = px
        m = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
        if abs(np.linalg.det(m)) < 1e-12:
            continue
        l12 = np.linalg.solve(m, (q - a).T).T
        bary = np.column_stack([1 - l12.sum(1), l12])
        ok = (bary >= -0.05).all(1)
        if not ok.any():
            continue
        # texels just past an edge are clamped onto the triangle; the weights must be renormalised,
        # or the point is scaled towards the world origin, i.e. into the body
        bw = np.clip(bary[ok], 0, 1)
        bw /= bw.sum(1, keepdims=True)
        ys_all.append(ys.ravel()[ok])
        xs_all.append(xs.ravel()[ok])
        pts_all.append(bw @ P)
        if attr is not None:
            att_all.append(bw @ attr[list(lt.vertices)])
    if not pts_all:
        return None
    out = (np.concatenate(ys_all), np.concatenate(xs_all), np.concatenate(pts_all))
    return out + ((np.concatenate(att_all),) if attr is not None else ())


def main():
    raw = sys.argv[sys.argv.index("--") + 1:]
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--layers", default="")
    p.add_argument("--out-dir", type=Path, required=True)
    a = p.parse_args(raw)
    base.clear_scene()
    objects = base.import_dressed_glb(a.input, 0.01)
    body = next(o for o in objects if "body" in o.name.lower())
    keep = {x.strip().lower() for x in a.layers.split(",") if x.strip()}
    garments = [o for o in objects if o is not body and
                (not keep or base.normalized_object_name(o.name).split("_")[0] in keep)]
    bpy.context.view_layer.update()
    bv = world(body)
    bf = np.array([t.vertices[:] for t in body.data.loop_triangles], np.int64)
    tree = BVHTree.FromPolygons(bv.tolist(), bf.tolist())
    meta = json.loads((a.out_dir / "bake.json").read_text())
    for g in garments:
        name = base.normalized_object_name(g.name)
        m = next((x for x in meta["meshes"] if x["name"] == name), None)
        if m is None:
            continue
        co = world(g)
        # per-vertex distance to the body picks the triangles worth testing texel by texel
        near = np.array([tree.find_nearest(Vector(v.tolist()))[3] or 1.0 for v in co]) < NEAR
        cand = [i for i, t in enumerate(g.data.loop_triangles) if near[list(t.vertices)].any()]
        for key in ("tex", "tex_back"):
            tex = a.out_dir / m[key]
            img = bpy.data.images.load(str(tex))
            size = img.size[0]
            bpy.data.images.remove(img)
            hid = np.zeros((size, size), bool)
            got = texel_points(g, co, size, cand)
            if got is not None:
                ys, xs, pts = got
                hid[ys, xs] = inside(pts, bv, bf)
            np.save(tex.with_suffix(".hidden.npy"), hid)
            print(f"hidden {name} {key}: {int((hid > 0).sum())} texels inside the body", flush=True)
    body_covered(body, garments, a.out_dir, meta)
    (a.out_dir / "hidden.done").write_text("ok")


def body_covered(body, garments, out_dir, meta):
    """Skin with cloth lying right on top of it bakes dark and would ring every poke."""
    m = next((x for x in meta["meshes"] if x["name"] == "body"), None)
    if m is None or not garments:
        return
    uv = body.data.uv_layers.new(name="bake")
    if not bake_case.smplx_uv(body, uv):
        return
    verts, polys, off = [], [], 0
    for g in garments:
        co = world(g)
        verts.append(co)
        polys.append(np.array([t.vertices[:] for t in g.data.loop_triangles]) + off)
        off += len(co)
    gtree = BVHTree.FromPolygons(np.concatenate(verts).tolist(), np.concatenate(polys).tolist())
    co, nr = world(body, normals=True)
    near = np.array([(gtree.find_nearest(Vector(v.tolist()))[3] or 1.0) for v in co]) < 0.01
    cand = [i for i, t in enumerate(body.data.loop_triangles) if near[list(t.vertices)].any()]
    tex = out_dir / m["tex"]
    img = bpy.data.images.load(str(tex))
    size = img.size[0]
    bpy.data.images.remove(img)
    half = size // 2                       # tested at half resolution, then upsampled
    hid = np.zeros((half, half), bool)
    got = texel_points(body, co, half, cand, uv_name="bake", attr=nr)
    if got is not None:
        for y, x, pt, n in zip(*got):
            d = Vector(n.tolist()).normalized()
            if gtree.ray_cast(Vector(pt.tolist()) + d * 1e-4, d, COVER)[0] is not None:
                hid[y, x] = True
    hid = np.repeat(np.repeat(hid, 2, 0), 2, 1)
    np.save(tex.with_suffix(".hidden.npy"), hid)
    print(f"hidden body: {int(hid.sum())} texels under snug cloth", flush=True)


if __name__ == "__main__":
    main()
