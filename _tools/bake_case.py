#!/usr/bin/env python3
"""Bake our Cycles render into textures for the real-time web viewer.

Scene = render/blender_render_garment_no_tone.py (transparent studio): same GLB
import, atlases, body skin, HDRI + ambient fill, Cycles. Each surface gets its
final display colour baked per texel, with the renderer's colour management:
body -> AgX Medium High Contrast, garments -> Standard at --garment-exposure.
Garments are baked on both sides (normals as-is and flipped), so the viewer
shows cloth two-sided exactly like Cycles does.

    blender --background --python bake_case.py -- \
        --input garment_final_pose.glb --atlas-root inputs_x/case/layers --out-dir web/case
"""
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

RENDER = Path("/home/nanxiangjiang/agentic_garment/DressAnything/render")
_spec = importlib.util.spec_from_file_location(
    "da_garment_no_tone", RENDER / "blender_render_garment_no_tone.py")
nt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nt)
base = nt.base


def parse():
    raw = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--atlas-root", type=Path)
    p.add_argument("--no-atlas", action="store_true")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--samples", type=int, default=512)
    p.add_argument("--body-res", type=int, default=4096)
    p.add_argument("--garment-scale", type=float, default=1.0,
                   help="baked texture size relative to the source atlas")
    p.add_argument("--garment-min", type=int, default=1024)
    p.add_argument("--garment-max", type=int, default=4096)
    p.add_argument("--inner-scale", type=float, default=0.5)
    p.add_argument("--garment-exposure", type=float, default=-1.5)
    p.add_argument("--hide-body", action="store_true")
    p.add_argument("--layers", default="",
                   help="peel state: comma list of layer ids to keep (e.g. L0,L1); default all")
    p.add_argument("--no-mesh", action="store_true", help="skip the mesh.glb export")
    return p.parse_args(raw)


def pow2ish(x, lo, hi):
    x = int(min(max(x, lo), hi))
    return (x + 63) // 64 * 64


def active_image_node(obj, image):
    """Bake target: an unconnected image node made active in every material slot."""
    for slot in obj.material_slots:
        mat = slot.material
        nodes = mat.node_tree.nodes
        node = nodes.get("BakeTarget") or nodes.new("ShaderNodeTexImage")
        node.name = "BakeTarget"
        node.image = image
        for n in nodes:
            n.select = False
        node.select = True
        nodes.active = node


def bake_to(obj, image, uv_name, samples):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers[uv_name]
    active_image_node(obj, image)
    scene = bpy.context.scene
    scene.cycles.samples = samples
    scene.render.bake.margin = 16
    scene.render.bake.margin_type = "ADJACENT_FACES"
    scene.render.bake.use_clear = True
    scene.render.bake.target = "IMAGE_TEXTURES"
    bpy.ops.object.bake(type="COMBINED", pass_filter={
        "EMIT", "DIRECT", "INDIRECT", "COLOR", "DIFFUSE", "GLOSSY", "TRANSMISSION"},
        margin=16, use_clear=True)


def save_display(image, path, agx, exposure):
    """Write a float bake through the renderer's view transform."""
    scene = bpy.context.scene
    vs = scene.view_settings
    if agx:
        vs.view_transform, vs.look = "AgX", "AgX - Medium High Contrast"
    else:
        vs.view_transform, vs.look = "Standard", "None"
    vs.exposure, vs.gamma = exposure, 1.0
    settings = scene.render.image_settings
    settings.file_format, settings.color_mode, settings.color_depth = "PNG", "RGB", "8"
    image.save_render(filepath=str(path), scene=scene)


def smplx_uv(body, uv):
    """Official SMPL-X UV layout, matched face by face on vertex triples."""
    # SMPL-X assets are licensed; read them in place, never copy into the site repo
    path = Path("/data/nanxiangjiang/baselines/PEAR/assets/SMPLX/smplx_uv.obj")
    vts, faces = [], {}
    for line in path.read_text().splitlines():
        if line.startswith("vt "):
            vts.append(tuple(map(float, line.split()[1:3])))
        elif line.startswith("f "):
            corners = [tuple(int(x) - 1 for x in c.split("/")[:2]) for c in line.split()[1:]]
            faces[frozenset(v for v, _ in corners)] = dict(corners)
    me = body.data
    if len(me.vertices) != 10475:
        print("body is not SMPL-X; smart UV fallback")
        return False
    miss = 0
    for poly in me.polygons:
        f = faces.get(frozenset(me.loops[i].vertex_index for i in poly.loop_indices))
        if f is None:
            miss += 1
            continue
        for i in poly.loop_indices:
            uv.data[i].uv = vts[f[me.loops[i].vertex_index]]
    print(f"SMPL-X UV: {len(me.polygons) - miss}/{len(me.polygons)} faces matched")
    return miss == 0


def dump_uv(obj, uv_name, path):
    me = obj.data
    me.calc_loop_triangles()
    uv = me.uv_layers[uv_name].data
    tris = np.array([[uv[l].uv[:] for l in t.loops] for t in me.loop_triangles], np.float32)
    np.save(path, tris)


def flip(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def main():
    args = parse()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    base.clear_scene()
    objects = base.import_dressed_glb(args.input, 0.01)
    if not args.no_atlas:
        base.apply_source_atlases(objects, args.atlas_root)
    base.style_body(objects)
    body = next((o for o in objects if "body" in o.name.lower()), None)
    garments = [o for o in objects if o is not body]
    if args.layers:
        keep = {x.strip().lower() for x in args.layers.split(",")}
        drop = [g for g in garments if base.normalized_object_name(g.name).split("_")[0] not in keep]
        garments = [g for g in garments if g not in drop]
        objects = [o for o in objects if o not in drop]
        for g in drop:
            print("peel: drop", g.name)
            bpy.data.objects.remove(g, do_unlink=True)
    base.setup_lighting(base.HERE / "studio_small_09_4k.exr", 1.5, 0.0, 2.0)
    base.configure_cycles("AUTO", args.samples)
    scene = bpy.context.scene
    scene.render.film_transparent = True

    meta = {"input": str(args.input), "atlas_root": str(args.atlas_root), "meshes": []}

    # body: its own UV for the bake
    if body is not None and not args.hide_body:
        bpy.context.view_layer.objects.active = body
        uv = body.data.uv_layers.new(name="bake")
        body.data.uv_layers.active = uv
        if not smplx_uv(body, uv):
            for o in bpy.context.view_layer.objects:
                o.select_set(o is body)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
            bpy.ops.object.mode_set(mode="OBJECT")
        img = bpy.data.images.new("body_bake", args.body_res, args.body_res, float_buffer=True)
        bake_to(body, img, "bake", args.samples)
        save_display(img, out / "body.png", agx=True, exposure=0.0)
        dump_uv(body, "bake", out / "body.uv.npy")
        meta["meshes"].append({"name": "body", "uv": "bake", "tex": "body.png"})
        print("baked body", flush=True)

    for g in garments:
        uv0 = g.data.uv_layers[0].name
        src = None
        for n in g.material_slots[0].material.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.name != "BakeTarget":
                src = n.image
        side = src.size[0] if src else 2048
        res = pow2ish(side * args.garment_scale, args.garment_min, args.garment_max)
        res_in = pow2ish(res * args.inner_scale, 512, args.garment_max)
        name = base.normalized_object_name(g.name)
        # outer = side the normals point to
        img = bpy.data.images.new(f"{name}_a", res, res, float_buffer=True)
        bake_to(g, img, uv0, args.samples)
        save_display(img, out / f"{name}_a.png", agx=False, exposure=args.garment_exposure)
        dump_uv(g, uv0, out / f"{name}.uv.npy")
        flip(g)
        img = bpy.data.images.new(f"{name}_b", res_in, res_in, float_buffer=True)
        bake_to(g, img, uv0, args.samples)
        save_display(img, out / f"{name}_b.png", agx=False, exposure=args.garment_exposure)
        flip(g)
        meta["meshes"].append({"name": name, "uv": uv0, "tex": f"{name}_a.png",
                               "tex_back": f"{name}_b.png", "res": [res, res_in]})
        print(f"baked {name} {res}/{res_in}", flush=True)

    # geometry for the viewer: positions + the bake UV, no materials
    for o in bpy.context.view_layer.objects:
        o.select_set(o in objects)
    for m in meta["meshes"]:
        obj = body if m["name"] == "body" else next(
            g for g in garments if base.normalized_object_name(g.name) == m["name"])
        # keep only the UV the texture was baked on
        for layer in list(obj.data.uv_layers):
            if layer.name != m["uv"]:
                obj.data.uv_layers.remove(layer)
        obj.data.materials.clear()
        obj.name = m["name"]
    if args.hide_body and body is not None:
        bpy.data.objects.remove(body, do_unlink=True)
    if not args.no_mesh:
        bpy.ops.export_scene.gltf(
            filepath=str(out / "mesh.glb"), export_format="GLB", use_selection=False,
            export_materials="NONE", export_normals=False, export_texcoords=True,
            export_apply=True, export_yup=True,
            export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=7,
            export_draco_position_quantization=14, export_draco_texcoord_quantization=14)
    (out / "bake.json").write_text(json.dumps(meta, indent=1))
    import subprocess
    subprocess.run([nt.compositor_python(), str(Path(__file__).resolve().parent / "seam_fill.py"),
                    str(out)], check=True)
    print("bake done", out)


if __name__ == "__main__":
    main()
