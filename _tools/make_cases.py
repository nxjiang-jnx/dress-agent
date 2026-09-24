#!/usr/bin/env python3
"""Write cases.json: which GLB, atlas, photo and agent plan each web result uses.
Sources follow provenance.json (traced from the wrapped_sim inputs)."""
import json
from pathlib import Path

DA = Path("/home/nanxiangjiang/agentic_garment/DressAnything")
R = Path("/data/nanxiangjiang/homepage_renders")
TOOLS = Path(__file__).resolve().parent
W = Path("/data/nanxiangjiang/baselines/_wild")

# display order: the two lead examples, then one category (photo set) after another
LEAD = ["appendix7", "experiment3"]
GROUPS = [["appendix1", "appendix2", "appendix3", "appendix4", "appendix5", "appendix7"],
          [f"experiment{n}" for n in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11)],
          [f"newjeans{n}" for n in range(1, 6)], [f"mountain{n}" for n in range(1, 6)],
          [f"africa{n}" for n in range(1, 6)], [f"dance{n}" for n in range(1, 6)]]
ORDER = LEAD + [c for g in GROUPS for c in g if c not in LEAD]
POSE = {"dance1", "dance2", "dance3", "dance4", "dance5", "experiment6", "experiment8",
        "experiment9", "experiment10", "mountain4", "mountain5"}
DRESS = {"africa1", "africa3", "africa4", "africa5", "newjeans1"}
BODY = {"experiment11"}
# repose of these missed the first piece of the base layer as a collider; re-run in wsim/repose_fix
REPOSE_FIX = {"mountain3", "mountain5"}
WS = DA / "wrapped_sim"
# hand-picked crops of the group photos that show the whole person (the case inputs are tight strips)
PHOTOS = R / "photos"


def source(case):
    s = case.rstrip("0123456789")
    s = {"experiment": "expnew"}.get(s, s)
    if s == "dance":
        demo = DA / "demos/dance" / case
        glb = demo / "final/render/reposed/garment_final_pose.glb"
    elif s == "expnew":
        demo = DA / "demos/experiment" / case
        n = int(case[10:])
        if n in (1, 4):          # paper GLBs were lost; rebuilt from inputs_expnew
            glb = R / "wsim/outputs_expnew" / case / "reposed/garment_final_pose.glb"
        elif n in (2, 3, 5):     # same drape, body and target as the paper run
            glb = demo / f"repose/out/{case}/garment_final_pose.glb"
        else:
            glb = demo / "final/render/reposed/garment_final_pose.glb"
    elif s == "appendix":
        n = case[8:]
        demo = DA / "demos_appendix" / n
        glb = demo / "final/render/reposed/garment_final_pose.glb"
        inputs = WS / "v1/inputs_appendix" / n
        manifest = json.loads((inputs / "manifest.json").read_text())
        # the GLB was draped in wrapped_sim from the latest design, so its patterns are there too
        pattern = {"drape": str(WS / "v1/outputs_appendix" / n), "inputs": str(inputs)}
        return s, demo, glb, inputs / "layers", [l["id"] for l in manifest["layers"]], pattern
    else:
        demo = DA / "demos_new" / s / case
        glb = demo / "final/render/reposed/garment_final_pose.glb"
        if case in REPOSE_FIX:
            glb = R / "wsim/repose_fix/out" / case / "garment_final_pose.glb"
    atlas = DA / f"wrapped_sim/inputs_{s}/{case}/layers"
    if case == "newjeans3":      # inputs_newjeans was regenerated; these match the GLB
        atlas = R / "atlas_shims/newjeans3/layers"
    manifest = json.loads((DA / f"wrapped_sim/inputs_{s}/{case}/manifest.json").read_text())
    layers = [l["id"] for l in manifest["layers"]]
    pattern = {"final": str(demo / "final")}
    if case == "experiment1":    # final/best holds an older design; the GLB is the wsim drape
        pattern = {"drape": str(R / "wsim/outputs_expnew" / case), "inputs": str(WS / "inputs_expnew" / case)}
    return s, demo, glb, atlas, layers, pattern


def main():
    gallery = []
    for case in ORDER:
        s, demo, glb, atlas, layers, pattern = source(case)
        photo = demo / "input.png"
        if (PHOTOS / f"{case}.png").is_file():
            photo = PHOTOS / f"{case}.png"
        cut = None
        if s == "expnew" and int(case[10:]) >= 6:
            cut, photo = photo, None   # these inputs are already cut out
        tags, chips = [], []
        if len(layers) > 1:
            tags.append("layered")
        if case in POSE:
            tags.append("pose"); chips.append("Dynamic pose")
        if case in DRESS:
            tags.append("dress"); chips.append("Dress")
        if case in BODY:
            tags.append("body"); chips.append("Plus size")
        gallery.append({
            "id": case, "set": s, "glb": str(glb), "atlas_root": str(atlas),
            "photo": str(photo) if photo else None, "cutout": str(cut) if cut else None,
            "layers_json": str(demo / "layers.json"), "tags": tags, "chips": chips,
            "states": [layers[:k + 1] for k in range(len(layers))], "pattern": pattern,
        })
    methods = [
        {"id": "dresscode", "label": "DressCode", "color": "#70ad47"},
        {"id": "chatgarment", "label": "ChatGarment", "color": "#f7c56e"},
        {"id": "isp", "label": "ISP", "color": "#69addc"},
        {"id": "garmentrecovery", "label": "GarmentRecovery", "color": "#4c74b1"},
        {"id": "ours", "label": "Ours", "color": "#fa9d57"},
    ]
    labels = {1: "Tee & shorts", 2: "Jersey", 3: "Layered tees", 4: "Cropped blazer", 5: "Vest & jacket",
              6: "Crouch", 8: "Sitting", 9: "Squat", 10: "Kneeling", 11: "Plus size"}

    def cmp_case(n):
        inp = (R / f"cutouts/experiment{n}_input_cutout_from_comparison_pdf.png" if n <= 5
               else DA / f"demos/experiment/experiment{n}/input.png")
        return {"id": f"experiment{n}", "label": labels[n], "input_src": str(inp)}

    data = {
        "default": LEAD[0],
        "filters": [{"id": "all", "label": "All"}, {"id": "layered", "label": "Multi-layer"},
                    {"id": "pose", "label": "Dynamic poses"}, {"id": "dress", "label": "Dresses & robes"}],
        "gallery": gallery,
        "compare": {
            "methods": methods,
            "rows": [{"id": "dressed", "label": "Avatar"}, {"id": "garment", "label": "Mesh"}],
            # the default scene of each group (Cropped blazer, Kneeling) leads its buttons
            "groups": {"layered": [cmp_case(n) for n in (4, 1, 2, 3, 5)],
                       "poses": [cmp_case(n) for n in (10, 6, 8, 9, 11)]},
            "ours_glb": {f"experiment{n}": [str(source(f"experiment{n}")[2]), str(source(f"experiment{n}")[3])]
                         for n in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11)},
        },
    }
    (TOOLS / "cases.json").write_text(json.dumps(data, indent=1))
    missing = [c["id"] for c in gallery if not Path(c["glb"]).is_file()]
    print("cases:", len(gallery), "missing glb:", missing)
    print("states:", sum(len(c["states"]) for c in gallery))


if __name__ == "__main__":
    main()
