# Building the result assets

Everything shown on the page comes from `DressAnything/render/blender_render_garment_no_tone.py`,
the renderer behind `render/run.bash` (transparent studio, AgX body, Standard garments at -1.5 EV).
Jekyll skips this folder, so it is not published.

| script | what it does |
| --- | --- |
| `make_cases.py` | writes `cases.json`: GLB, atlas root, photo and agent layer plan of every result |
| `orbit_render.py` | Blender turntable through the renderer; only the camera orbits (fixed radius, fitted to every azimuth) |
| `bake_case.py` | bakes the same Cycles scene per texel for the WebGL viewer (body AgX, garments Standard; body and cloth are baked on both sides so back faces, e.g. an open mouth, look as in Cycles); `--layers L0,L1` bakes a peeled state |
| `seam_fill.py` | refills island borders and gutters of a bake from the island interior; on the body it also clears the black eye sockets and the lid-hidden eyeball texels, which mipmaps would otherwise bleed into a dark eye ring |
| `hidden_masks.py` | per texel, finds cloth inside the body and skin with cloth lying on it; `seam_fill.py` refills those texels (and a 2.5 mm band beside them) from visible, lit surface, so pokes through snug cloth show no dark ring |
| `pattern_states.py` | the 3D sewing-pattern still of every peel state (paper_vis sheets, same Cycles studio); one camera and crop per case, so the stills overlay exactly; `--drape/--inputs` reads a wrapped_sim drape instead of `final/best` |
| `run_jobs.py` | drains a job queue on one GPU; run one per GPU (2 and 3) |
| `build_site.py` | frames to H.264 + VP9 video and posters, bakes to WebP, writes `static/data/*.json` |
| `shot.py` | headless screenshots for checking the page |

Order: `make_cases.py`, queue jobs, `run_jobs.py queue.json --gpu 2` and `--gpu 3`
(bakes: `bake_case.py`, then `--body-inner-only`, then `hidden_masks.py` and `seam_fill.py`),
`pattern_states.py` per case, then `build_site.py gallery` and `build_site.py compare`.
For a few new cases, `/data/nanxiangjiang/homepage_renders/queues/case_all.py GPU case...` runs the
whole chain (turntable, bake, body inside, hidden masks, seam fill) one case after another;
`build_site.py gallery --partial` then packs every case whose bakes and patterns are done.

Sources (traced from `wrapped_sim/inputs_*`):

* dance: `demos/dance/<case>/final/render/reposed/garment_final_pose.glb`
* africa, mountain, newjeans: `demos_new/<set>/<case>/final/render/reposed/garment_final_pose.glb`
* experiment 6, 8-11: `demos/experiment/<case>/final/render/reposed/garment_final_pose.glb`
* experiment 2, 3, 5: `demos/experiment/<case>/repose/out/<case>/garment_final_pose.glb`
  (the paper-time GLBs were deleted; these share the drape, body and target of that run)
* experiment 1, 4: rebuilt from `wrapped_sim/inputs_expnew` with `wrapped_sim/drape.py` (exp 1 only)
  and `wrapped_sim/repose.py` into `/data/nanxiangjiang/homepage_renders/wsim`; both match the paper figure
* appendix: `demos_appendix/<n>/final/render/reposed/garment_final_pose.glb`, atlases and patterns from
  `wrapped_sim/v1/{inputs,outputs}_appendix/<n>` (the GLB was draped there; final/best of case 4 is an older design)
* mountain3, mountain5: re-reposed into `/data/nanxiangjiang/homepage_renders/wsim/repose_fix/out` with the 08-29
  repose and its saved sim props. Their base-layer drape jobs named the first piece by its refine-stage folder, so
  repose never made it a collider for the second piece: the skirt slid inside the tucked tee (mountain3) and the
  untucked tee slid inside the pants (mountain5). `repose_fix/run_fix.py` renames the collider and re-runs
* patterns: `final/best` of each case, except experiment1 (`wsim/outputs_expnew`) and appendix (see above)
* newjeans3 atlases: the textures of `demos_new/newjeans/newjeans3/final/texture`, which match its GLB
* baselines: `/data/nanxiangjiang/baselines/_wild/<Method>/wild<N>/studio.glb`
  (DressCode: `posed/studio.glb`; ISP and GarmentRecovery wild4: `wild4full`), wild N = experiment N

Raw frames and bakes live in `/data/nanxiangjiang/homepage_renders`.
