#!/usr/bin/env python3
"""Turntable frames through the DressAnything renderer.

Everything but the camera comes from render/blender_render_garment_no_tone.py,
i.e. the exact render/run.bash setup: GLB import, source atlases, body skin,
HDRI + ambient fill, Cycles, AgX body pass + Standard garment pass at
--garment-exposure, garment mask, transparent composite.
The camera orbits on one fixed-radius sphere around the subject, so the figure
stays centred and keeps its scale across views.

    blender --background --python orbit_render.py -- \
        --input garment_final_pose.glb --atlas-root inputs_x/case/layers \
        --out-dir frames/ --count 144 --elevation 2
"""
import argparse
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

RENDER = Path("/home/nanxiangjiang/agentic_garment/DressAnything/render")
_spec = importlib.util.spec_from_file_location(
    "da_garment_no_tone", RENDER / "blender_render_garment_no_tone.py")
nt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nt)
base = nt.base
HERE = Path(__file__).resolve().parent


def parse():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--atlas-root", type=Path)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--count", type=int, default=144, help="azimuth steps over 360 deg")
    p.add_argument("--start", type=float, default=0.0, help="first azimuth, 0 = front")
    p.add_argument("--elevation", type=float, default=2.0)
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--height", type=int, default=900)
    p.add_argument("--samples", type=int, default=128)
    p.add_argument("--garment-exposure", type=float, default=-1.5)
    p.add_argument("--hdri-strength", type=float, default=1.5)
    p.add_argument("--ambient-strength", type=float, default=2.0)
    p.add_argument("--hdri-follow", action="store_true",
                   help="rotate the HDRI with the camera (turntable lighting)")
    p.add_argument("--hide-body", action="store_true")
    p.add_argument("--no-atlas", action="store_true", help="keep GLB materials")
    p.add_argument("--margin", type=float, default=1.04)
    p.add_argument("--frame-json", type=Path,
                   help="reuse centre/distance from this json (shared framing)")
    p.add_argument("--frames", default="", help="comma list of frame indices to render")
    p.add_argument("--skip-existing", action="store_true")
    p.add_argument("--layers", default="", help="keep only these garment layers (peel state)")
    p.add_argument("--cpu-denoise", action="store_true",
                   help="run OIDN on the CPU (Blender's default); the GPU run matches it to 1/255")
    return p.parse_args(raw)


def mesh_points(objects, limit=60000):
    pts = []
    for obj in objects:
        n = len(obj.data.vertices)
        co = np.empty(n * 3, np.float64)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape(n, 3)
        m = np.asarray(obj.matrix_world, np.float64)
        pts.append(co @ m[:3, :3].T + m[:3, 3])
    pts = np.concatenate(pts)
    if len(pts) > limit:
        pts = pts[np.random.default_rng(0).choice(len(pts), limit, replace=False)]
    return pts


def view_dir(az, el):
    a, e = math.radians(az), math.radians(el)
    # az 0 = front (camera on -Y), matching base.horizontal_view_direction
    return np.array([math.cos(e) * math.sin(a), -math.cos(e) * math.cos(a), math.sin(e)])


def fit_distance(pts, center, azs, el, th, tv):
    q = pts - center
    need = 0.0
    for az in azs:
        d = view_dir(az, el)
        r = np.cross(-d, [0, 0, 1.0]); r /= np.linalg.norm(r)
        u = np.cross(r, -d)
        need = max(need, float(np.max(q @ d + np.maximum(np.abs(q @ r) / th, np.abs(q @ u) / tv))))
    return need


def place(camera, center, dist, az, el):
    d = Vector(view_dir(az, el).tolist())
    camera.location = center + d * dist
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()


def main():
    args = parse()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    azs = [(args.start + 360.0 * i / args.count) % 360.0 for i in range(args.count)]
    todo = list(range(args.count))
    if args.frames:
        todo = [int(x) for x in args.frames.split(",")]
    out = lambda i: args.out_dir / f"f{i:03d}.png"
    if args.skip_existing:
        todo = [i for i in todo if not out(i).is_file()]
    if not todo:
        print("nothing to render")
        return

    base.clear_scene()
    objects = base.import_dressed_glb(args.input, 0.01)
    if not args.no_atlas:
        base.apply_source_atlases(objects, args.atlas_root)
    base.style_body(objects)
    if args.layers:
        keep = {x.strip().lower() for x in args.layers.split(",")}
        drop = [o for o in objects if "body" not in o.name.lower()
                and base.normalized_object_name(o.name).split("_")[0] not in keep]
        objects = [o for o in objects if o not in drop]
        for o in drop:
            bpy.data.objects.remove(o, do_unlink=True)
    garments = [o for o in objects if "body" not in o.name.lower()]

    # framing from the dressed subject (body included), as the renderer does
    lens, sensor = 58.0, 36.0
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    aspect = args.width / args.height
    # sensor spans the larger image side
    tl = sensor / (2 * lens)
    th, tv = (tl, tl / aspect) if aspect >= 1 else (tl * aspect, tl)
    if args.frame_json and args.frame_json.is_file():
        fr = json.loads(args.frame_json.read_text())
        center, dist = Vector(fr["center"]), fr["distance"]
    else:
        pts = mesh_points(objects)
        lo, hi = pts.min(0), pts.max(0)
        center = Vector(((lo + hi) / 2).tolist())
        dist = fit_distance(pts, np.array(center), [i * 2.5 for i in range(144)],
                            args.elevation, th, tv) * args.margin
        if args.frame_json:
            args.frame_json.write_text(json.dumps({"center": list(center), "distance": dist}))
    print(f"orbit centre={tuple(round(c, 3) for c in center)} distance={dist:.3f}")

    if args.hide_body:
        objects = base.drop_body(objects)
    base.setup_lighting(base.HERE / "studio_small_09_4k.exr", args.hdri_strength, 0.0,
                        args.ambient_strength)
    mapping = next(n for n in scene.world.node_tree.nodes if n.type == "MAPPING")
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.data.lens = lens
    camera.data.sensor_width = sensor
    camera.data.sensor_fit = "AUTO"
    scene.camera = camera
    base.configure_cycles("AUTO", args.samples)
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    # only the camera moves between frames: keep the synced scene and BVH
    scene.render.use_persistent_data = True
    scene.cycles.denoising_use_gpu = not args.cpu_denoise

    with tempfile.TemporaryDirectory(prefix="orbit-", dir="/data/nanxiangjiang/tmp") as tmp:
        tmp = Path(tmp)
        base.setup_render(tmp / "beauty.png", True, no_tone_mapping=False)
        for k, i in enumerate(todo):
            place(camera, center, dist, azs[i], args.elevation)
            # Mapping POINT rotation samples E(R d): -az turns the map with the camera
            mapping.inputs["Rotation"].default_value[2] = math.radians(-azs[i]) if args.hdri_follow else 0.0
            bpy.ops.render.render(write_still=False)
            nt.save_render_as(tmp / f"agx_{i:03d}.png", False, 0.0)
            nt.save_render_as(tmp / f"std_{i:03d}.png", True, args.garment_exposure)
            print(f"beauty {k + 1}/{len(todo)} az={azs[i]:.1f}", flush=True)
        nt.configure_mask_scene(garments, tmp / "mask.png")
        for k, i in enumerate(todo):
            place(camera, center, dist, azs[i], args.elevation)
            scene.render.filepath = str(tmp / f"mask_{i:03d}.png")
            bpy.ops.render.render(write_still=True)
        jobs = [[str(tmp / f"agx_{i:03d}.png"), str(tmp / f"std_{i:03d}.png"),
                 str(tmp / f"mask_{i:03d}.png"), str(out(i))] for i in todo]
        (tmp / "jobs.json").write_text(json.dumps(jobs))
        subprocess.run([nt.compositor_python(), str(HERE / "composite_batch.py"),
                        str(tmp / "jobs.json")], check=True)
    (args.out_dir / "orbit.json").write_text(json.dumps({
        "input": str(args.input), "atlas_root": str(args.atlas_root), "count": args.count,
        "start": args.start, "elevation": args.elevation, "center": list(center),
        "distance": dist, "size": [args.width, args.height], "samples": args.samples,
        "garment_exposure": args.garment_exposure, "hdri_follow": args.hdri_follow,
        "hide_body": args.hide_body}, indent=1))
    print("orbit done", args.out_dir)


if __name__ == "__main__":
    main()
