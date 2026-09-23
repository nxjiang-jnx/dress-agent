# Building the result assets

Everything shown on the page comes from `DressAnything/render/blender_render_garment_no_tone.py`,
the renderer behind `render/run.bash` (transparent studio, AgX body, Standard garments at -1.5 EV).
Jekyll skips this folder, so it is not published.

| script | what it does |
| --- | --- |
| `make_cases.py` | writes `cases.json`: GLB, atlas root, photo and agent layer plan of every result |
| `orbit_render.py` | Blender turntable through the renderer; only the camera orbits (fixed radius, fitted to every azimuth) |
| `bake_case.py` | bakes the same Cycles scene per texel for the WebGL viewer (body AgX, garments Standard, cloth baked on both sides); `--layers L0,L1` bakes a peeled state |
| `seam_fill.py` | refills island borders and gutters of a bake from the island interior |
| `run_jobs.py` | drains a job queue on one GPU; run one per GPU (2 and 3) |
| `build_site.py` | frames to H.264 + VP9 video and posters, bakes to WebP, writes `static/data/*.json` |
| `shot.py` | headless screenshots for checking the page |

Order: `make_cases.py`, queue jobs, `run_jobs.py queue.json --gpu 2` and `--gpu 3`,
then `build_site.py gallery` and `build_site.py compare`.

Sources (traced from `wrapped_sim/inputs_*`):

* dance: `demos/dance/<case>/final/render/reposed/garment_final_pose.glb`
* africa, mountain, newjeans: `demos_new/<set>/<case>/final/render/reposed/garment_final_pose.glb`
* experiment 6, 8-11: `demos/experiment/<case>/final/render/reposed/garment_final_pose.glb`
* experiment 2, 3, 5: `demos/experiment/<case>/repose/out/<case>/garment_final_pose.glb`
  (the paper-time GLBs were deleted; these share the drape, body and target of that run)
* experiment 1, 4: rebuilt from `wrapped_sim/inputs_expnew` with `wrapped_sim/drape.py` (exp 1 only)
  and `wrapped_sim/repose.py` into `/data/nanxiangjiang/homepage_renders/wsim`; both match the paper figure
* newjeans3 atlases: the textures of `demos_new/newjeans/newjeans3/final/texture`, which match its GLB
* baselines: `/data/nanxiangjiang/baselines/_wild/<Method>/wild<N>/studio.glb`
  (DressCode: `posed/studio.glb`; ISP and GarmentRecovery wild4: `wild4full`), wild N = experiment N

Raw frames and bakes live in `/data/nanxiangjiang/homepage_renders`.
