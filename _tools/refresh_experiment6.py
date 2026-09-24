#!/usr/bin/env python3
"""Install the verified experiment6 render and bake into the local website."""
import argparse
import json
import shutil
from pathlib import Path

from PIL import Image

from build_site import encode, to_webp


SITE = Path(__file__).resolve().parents[1]
RENDERS = Path("/data/nanxiangjiang/homepage_renders")


def complete_orbit(source):
    frames = sorted(source.glob("f[0-9][0-9][0-9].png"))
    if len(frames) != 180 or not (source / "orbit.json").is_file():
        raise RuntimeError(f"Incomplete 180-frame orbit: {source} ({len(frames)} frames)")


def install_video(source, output, size, gop):
    encode(source, output, size, gop)


def install_bake(bake, gallery):
    meta = json.loads((bake / "bake.json").read_text())
    out = gallery / "3d"
    state = out / "s0"
    state.mkdir(parents=True, exist_ok=True)
    for part in meta["meshes"]:
        name = part["name"]
        quality = 84 if name == "body" else 90
        to_webp(bake / part["tex"], state / f"{name}.webp", quality)
        if part.get("tex_back"):
            to_webp(bake / part["tex_back"], state / f"{name}_in.webp", 82)
        if name == "body":
            im = Image.open(bake / part["tex"]).convert("RGB")
            im.resize((im.width // 2, im.height // 2), Image.Resampling.LANCZOS).save(
                state / "body_m.webp", quality=84, method=6)
    shutil.copy2(bake / "mesh.glb", out / "mesh.glb")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bake-only", action="store_true")
    args = parser.parse_args()
    cid = "experiment6"
    gallery = SITE / "static/gallery" / cid
    compare = SITE / "static/compare" / cid
    gallery_frames = RENDERS / "gallery" / cid / "turntable_inward"
    garment_frames = RENDERS / "cmp" / cid / "ours" / "garment_webgl_inward"
    bake = RENDERS / "bake" / cid / "s0_inward"
    if not (bake / "seam.done").is_file() or not (bake / "mesh.glb").is_file():
        raise RuntimeError(f"Incomplete bake: {bake}")
    install_bake(bake, gallery)
    if args.bake_only:
        print("experiment6 website bake installed")
        return

    complete_orbit(gallery_frames)
    complete_orbit(garment_frames)
    install_video(gallery_frames,
                  gallery / "turntable.mp4", (480, 600), 48)
    install_video(gallery_frames, compare / "ours_dressed.mp4", (400, 500), 6)
    install_video(garment_frames, compare / "ours_garment.mp4", (400, 500), 6)
    print("experiment6 website assets installed")


if __name__ == "__main__":
    main()
