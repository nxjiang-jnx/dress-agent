#!/usr/bin/env python3
"""3D sewing-pattern images for every peel state of a result.

Same sheets, layout and Cycles studio as paper_vis/pattern_pieces.py --combined. One camera
and one crop, fitted to the whole outfit, serve every state, so peeling a layer off only
removes its sheets and nothing else moves.

    python pattern_states.py --final demos/.../final --states L0 L0,L1 --out patterns/<case>
    python pattern_states.py --drape outputs_<set>/<case> --inputs inputs_<set>/<case> ...

--drape/--inputs reads a wrapped_sim drape instead of final/best, for results whose GLB
was draped there from a newer design.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, "/home/nanxiangjiang/agentic_garment/paper_vis")
import pattern_pieces as pp                                      # noqa: E402
from render_figure_views import garmentcode_camera              # noqa: E402

sheets, tex = pp.sheets, pp.tex
SUFFIX = "_garmentcode_render"


def shim_final(drape: Path, inputs: Path, root: Path) -> Path:
    """final/ layout over a wrapped_sim drape: best/<L>/<job>, texture/<job>/atlas.png, designs/."""
    final = root / "final"
    (final / "designs").mkdir(parents=True)
    for layer in json.loads((inputs / "manifest.json").read_text())["layers"]:
        lid = layer["id"]
        jobs = [p for p in drape.glob(f"{lid}*{SUFFIX}") if p.name == lid + SUFFIX
                or p.name[len(lid):].startswith("_layer")]
        for job in jobs:
            name = job.name[: -len(SUFFIX)]
            k = int(name.rpartition("_layer")[2]) if "_layer" in name else 0
            (final / "best" / lid).mkdir(parents=True, exist_ok=True)
            (final / "best" / lid / job.name).symlink_to(job.resolve())
            (final / "texture" / name).mkdir(parents=True)
            (final / "texture" / name / "atlas.png").symlink_to((inputs / layer["atlases"][k]).resolve())
            (final / "designs" / f"{name}_design.json").symlink_to((inputs / layer["design"]).resolve())
    return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", type=Path)
    ap.add_argument("--drape", type=Path, help="wrapped_sim drape output (instead of --final)")
    ap.add_argument("--inputs", type=Path, help="its wrapped_sim input case")
    ap.add_argument("--states", required=True, nargs="+", help="comma lists of layer ids")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("--margin", type=float, default=1.10)
    ap.add_argument("--pad", type=int, default=20)
    ap.add_argument("--front-gap", type=float, default=8.0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pattern-states-") as tmp:
        final = shim_final(a.drape, a.inputs, Path(tmp)) if a.drape else a.final.resolve()
        garments = tex.worn_garments(final, final / "texture")
        if not garments:
            raise SystemExit(f"no garments under {final / 'best'}")
        built = []                                   # (layer id, job, cloud)
        for order, g in enumerate(garments):
            gap = a.front_gap if pp.open_front(final, g["name"]) else 0.0
            for _, job, cloud in pp.pieces_of(g, order, Path(tmp), front_gap=gap):
                built.append((g["order"][0], job, cloud))
        camera = garmentcode_camera(np.vstack([c for _, _, c in built]), yaw=sheets.YAW,
                                    pitch=sheets.PITCH, margin=a.margin)
        box = None
        # the full outfit first: it fixes the crop the other states share
        order = sorted(range(len(a.states)), key=lambda k: -len(a.states[k].split(",")))
        for k in order:
            keep = set(a.states[k].split(","))
            jobs = [job for layer, job, _ in built if layer in keep]
            full = Path(tmp) / f"s{k}_full.png"
            sheets.render(jobs, camera, full, a.size)
            im = Image.open(full).convert("RGBA")
            if box is None:
                ys, xs = np.nonzero(np.asarray(im)[..., 3] > 2)
                box = (max(int(xs.min()) - a.pad, 0), max(int(ys.min()) - a.pad, 0),
                       min(int(xs.max()) + a.pad + 1, im.size[0]), min(int(ys.max()) + a.pad + 1, im.size[1]))
            im.crop(box).save(a.out / f"s{k}.png")
            print(f"pattern s{k} ({a.states[k]}): {len(jobs)} sheet(s)", flush=True)
    (a.out / "done").write_text("ok")


if __name__ == "__main__":
    main()
