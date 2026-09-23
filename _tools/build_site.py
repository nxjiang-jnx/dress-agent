#!/usr/bin/env python3
"""Pack rendered frames and bakes into web assets + page data.

    python build_site.py gallery   # static/gallery/<case>/..., static/data/gallery.json
    python build_site.py compare   # static/compare/<case>/..., static/data/compare.json
"""
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

TOOLS = Path(__file__).resolve().parent
SITE = TOOLS.parent
RENDERS = Path("/data/nanxiangjiang/homepage_renders")
CASES = json.loads((TOOLS / "cases.json").read_text())


def flat(path, size=None):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    im = bg.convert("RGB")
    if size and im.size != tuple(size):
        im = im.resize(size, Image.LANCZOS)
    return im


def encode(frames_dir, out, size, gop, fps=24, crf=21):
    """H.264 .mp4 for Safari/Chrome/Firefox plus VP9 .webm for Chromium builds without
    H.264; the page picks one with canPlayType. Poster = first frame."""
    frames = sorted(Path(frames_dir).glob("f[0-9][0-9][0-9].png"))
    assert frames, frames_dir
    out.parent.mkdir(parents=True, exist_ok=True)
    w, h = size
    src = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    gopt = ["-g", str(gop), "-keyint_min", str(gop)]
    h264 = src + ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p",
                  "-sc_threshold", "0", "-movflags", "+faststart", "-tag:v", "avc1"] + gopt + [str(out)]
    vp9 = src + ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf + 12), "-row-mt", "1",
                 "-deadline", "good", "-cpu-used", "2", "-pix_fmt", "yuv420p"] + gopt + [
                 str(out.with_suffix(".webm"))]
    procs = [subprocess.Popen(c, stdin=subprocess.PIPE) for c in (h264, vp9)]
    with ThreadPoolExecutor(8) as ex:
        for im in ex.map(lambda f: flat(f, size), frames):
            buf = np.asarray(im).tobytes()
            for p in procs:
                p.stdin.write(buf)
    for p in procs:
        p.stdin.close()
        assert p.wait() == 0, out
    flat(frames[0], size).save(out.with_suffix(".webp"), quality=86, method=6)
    return len(frames)


def photo(src, out, height, cutout=False):
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        im = bg
    im = im.convert("RGB")
    if cutout:
        # trim white margins so the person fills the frame
        a = np.asarray(im.convert("L")) < 250
        ys, xs = np.where(a)
        if len(xs):
            pad = int(0.04 * im.size[1])
            im = im.crop((max(xs.min() - pad, 0), max(ys.min() - pad, 0),
                          min(xs.max() + pad, im.size[0]), min(ys.max() + pad, im.size[1])))
    if im.size[1] > height:
        im = im.resize((round(im.size[0] * height / im.size[1]), height), Image.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, quality=88, method=6)


def fresh(src, dst):
    return dst.is_file() and dst.stat().st_mtime > Path(src).stat().st_mtime


def to_webp(src, dst, q):
    if fresh(src, dst):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.open(src).convert("RGB").save(dst, quality=q, method=6)


def plan_rows(layers_json, meshes):
    """Layer plan from the agent's layers.json, matched to the baked mesh layers."""
    L = json.loads(Path(layers_json).read_text())
    if "order" in L:
        garments = L["garments"]
        groups = L["order"]["layers"]
    else:
        # older schema: flat garment list, plan.json names the base layer
        garments = L["layers"]
        plan = json.loads((Path(layers_json).parent / "plan.json").read_text())
        names = [g["name"] for g in garments]
        base = plan.get("base", [0])
        groups = [[names[i] for i in base]] + [[n] for i, n in enumerate(names) if i not in base]
    types = {g["name"]: g for g in garments}
    rows = []
    for i, names in enumerate(groups):
        notes = []
        for n in names:
            g = types.get(n, {})
            st = g.get("structure", g.get("wear", {}))
            bits = [g.get("type", "")]
            if st.get("closure") == "open" or st.get("open_front"):
                bits.append("open front")
            if st.get("tucked_into"):
                bits.append("tucked in")
            notes.append(", ".join(b for b in bits if b))
        rows.append({"names": names, "note": " · ".join(dict.fromkeys(notes)),
                     "kind": "base" if i == 0 else "outer"})
    summary = L.get("summary", "").strip()
    if summary:
        summary = summary[0].upper() + summary[1:]
        if not summary.endswith("."):
            summary += "."
    return rows, summary


def ready(c):
    bake = RENDERS / "bake" / c["id"]
    return (all((bake / f"s{k}" / "seam.done").is_file() for k in range(len(c["states"])))
            and (RENDERS / "patterns" / c["id"] / "done").is_file())


def patterns(cid, n, out, width=640):
    """Sewing-pattern stills, one per peel state; they share one crop, so they overlay exactly."""
    urls, size = [], None
    for k in range(n):
        im = Image.open(RENDERS / "patterns" / cid / f"s{k}.png").convert("RGBA")
        if im.size[0] > width:
            im = im.resize((width, round(im.size[1] * width / im.size[0])), Image.LANCZOS)
        dst = out / "pattern" / f"s{k}.webp"
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, quality=90, method=6)
        urls.append(f"static/gallery/{cid}/pattern/s{k}.webp")
        size = im.size
    return urls, list(size)


def gallery(only=None):
    items = []
    for c in CASES["gallery"]:
        cid = c["id"]
        if only is not None and not ready(c):
            print("skip (not rendered yet)", cid)
            continue
        out = SITE / "static" / "gallery" / cid
        # turntable
        frames = RENDERS / "gallery" / cid / "turntable"
        if only is None or (not (out / "turntable.mp4").is_file() and (frames / "orbit.json").is_file()):
            encode(frames, out / "turntable.mp4", (480, 600), gop=48)
        # photos
        src = c.get("cutout") or c["photo"]
        photo(src, out / "photo.webp", 1200, cutout=bool(c.get("cutout")))
        photo(src, out / "thumb.webp", 320, cutout=bool(c.get("cutout")))
        # 3D
        bake = RENDERS / "bake" / cid
        states = []
        for k, keep in enumerate(c["states"]):
            sdir = bake / f"s{k}"
            meta = json.loads((sdir / "bake.json").read_text())
            tex = {}
            for m in meta["meshes"]:
                q = 84 if m["name"] == "body" else 90
                to_webp(sdir / m["tex"], out / "3d" / f"s{k}" / f"{m['name']}.webp", q)
                if m["name"] == "body" and not fresh(sdir / m["tex"], out / "3d" / f"s{k}" / "body_m.webp"):
                    # phones get a 2K skin
                    im = Image.open(sdir / m["tex"]).convert("RGB")
                    im.resize((im.size[0] // 2, im.size[1] // 2), Image.LANCZOS).save(
                        out / "3d" / f"s{k}" / "body_m.webp", quality=84, method=6)
                if m.get("tex_back"):
                    to_webp(sdir / m["tex_back"], out / "3d" / f"s{k}" / f"{m['name']}_in.webp", 82)
                    tex[m["name"]] = [f"s{k}/{m['name']}.webp", f"s{k}/{m['name']}_in.webp"]
                else:
                    tex[m["name"]] = f"s{k}/{m['name']}.webp"
            states.append({"layers": keep, "tex": tex})
        shutil.copy(bake / f"s{len(c['states']) - 1}" / "mesh.glb", out / "3d" / "mesh.glb")
        pattern, pattern_size = patterns(cid, len(c["states"]), out)
        rows, summary = plan_rows(c["layers_json"], None)
        n = len(rows)
        items.append({
            "id": cid, "set": c["set"], "title": c.get("title") or summary,
            "layers": n, "tags": c["tags"], "chips": [f"{n} layer{'s' if n > 1 else ''}"] + c.get("chips", []),
            "photo": f"static/gallery/{cid}/photo.webp", "thumb": f"static/gallery/{cid}/thumb.webp",
            "cutout": bool(c.get("cutout")),
            "video": f"static/gallery/{cid}/turntable.mp4", "poster": f"static/gallery/{cid}/turntable.webp",
            "plan": rows, "pattern": pattern, "pattern_size": pattern_size,
            "model": {"dir": f"static/gallery/{cid}/3d/", "mesh": "mesh.glb", "states": states},
        })
        print("gallery", cid, flush=True)
    data = {"default": CASES.get("default", items[0]["id"]), "filters": CASES["filters"], "items": items}
    (SITE / "static" / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "static" / "data" / "gallery.json").write_text(json.dumps(data, indent=1))


def compare():
    cfg = CASES["compare"]
    for grp in cfg["groups"].values():
        for s in grp:
            cid = s["id"]
            out = SITE / "static" / "compare" / cid
            for m in cfg["methods"]:
                for r in cfg["rows"]:
                    encode(RENDERS / "cmp" / cid / m["id"] / r["id"], out / f"{m['id']}_{r['id']}.mp4",
                           (400, 500), gop=6, crf=22)
            photo(s["input_src"], out / "input.webp", 1000, cutout=True)
            photo(s["input_src"], out / "thumb.webp", 160, cutout=True)
            s["input"] = f"static/compare/{cid}/input.webp"
            s["thumb"] = f"static/compare/{cid}/thumb.webp"
            print("compare", cid, flush=True)
    data = {"dir": "static/compare/", "duration": 7.5, "input_color": "#d8514b",
            "default": {"layered": "experiment4", "poses": "experiment10"},
            "methods": cfg["methods"], "rows": cfg["rows"],
            "groups": {g: [{k: v for k, v in s.items() if k != "input_src"} for s in grp]
                       for g, grp in cfg["groups"].items()}}
    (SITE / "static" / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "static" / "data" / "compare.json").write_text(json.dumps(data, indent=1))


if __name__ == "__main__":
    # gallery [--partial]: --partial builds only the cases whose renders are finished
    if sys.argv[1] == "gallery":
        gallery("partial" if "--partial" in sys.argv else None)
    else:
        compare()
