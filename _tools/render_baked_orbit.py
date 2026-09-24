#!/usr/bin/env python3
"""Render a site's Cycles-baked model to comparison turntable frames."""
import argparse
import asyncio
import base64
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright


SITE = Path(__file__).resolve().parents[1]
INIT = r"""async ({width, height, count, distance, hideBody}) => {
  const THREE = await import('./static/js/vendor/three/three.module.min.js');
  const {GLTFLoader} = await import('./static/js/vendor/three/addons/loaders/GLTFLoader.js');
  const {DRACOLoader} = await import('./static/js/vendor/three/addons/loaders/DRACOLoader.js');
  const {bakedParts, setBaked} = await import('./static/js/bakedmat.js?v=20260923o');
  const canvas = document.createElement('canvas');
  document.body.appendChild(canvas);
  const renderer = new THREE.WebGLRenderer({canvas, antialias: true, preserveDrawingBuffer: true});
  renderer.setSize(width, height, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.setClearColor(0xffffff, 1);
  const loader = new GLTFLoader();
  const draco = new DRACOLoader();
  draco.setDecoderPath('./static/js/vendor/three/addons/libs/draco/gltf/');
  loader.setDRACOLoader(draco);
  const gltf = await loader.loadAsync('./static/gallery/experiment6/3d/mesh.glb');
  const root = gltf.scene;
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const center = box.getCenter(new THREE.Vector3());
  const meshes = [];
  root.traverse(o => { if (o.isMesh && !o.name.endsWith('_back')) meshes.push(o); });
  const textures = new THREE.TextureLoader();
  for (const mesh of meshes) {
    const name = mesh.name.toLowerCase();
    const body = name === 'body';
    const back = bakedParts(mesh, body);
    const path = './static/gallery/experiment6/3d/s0/' + name;
    const outer = await textures.loadAsync(path + '.webp');
    const inner = await textures.loadAsync(path + '_in.webp');
    for (const tex of [outer, inner]) { tex.colorSpace = THREE.SRGBColorSpace; tex.flipY = false; }
    setBaked(mesh, back, outer, inner, body);
    if (body && hideBody) mesh.visible = false;
  }
  const scene = new THREE.Scene();
  scene.add(root);
  const camera = new THREE.PerspectiveCamera(30, width / height, distance / 50, distance * 10);
  window.drawBakedOrbit = i => {
    const az = 2 * Math.PI * i / count;
    const el = THREE.MathUtils.degToRad(2);
    camera.position.set(center.x + distance * Math.cos(el) * Math.sin(az),
                        center.y + distance * Math.sin(el),
                        center.z + distance * Math.cos(el) * Math.cos(az));
    camera.lookAt(center);
    camera.updateProjectionMatrix();
    renderer.render(scene, camera);
    return canvas.toDataURL('image/png');
  };
  return center.toArray();
}"""


async def render(args, port):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=[
            "--use-gl=angle", "--use-angle=swiftshader",
            "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
        ])
        page = await browser.new_page()
        await page.goto(f"http://127.0.0.1:{port}/", wait_until="domcontentloaded", timeout=90000)
        center = await page.evaluate(INIT, {
            "width": args.width, "height": args.height, "count": args.count,
            "distance": args.distance, "hideBody": args.hide_body,
        })
        for i in range(args.count):
            encoded = await page.evaluate("i => window.drawBakedOrbit(i)", i)
            (args.output / f"f{i:03d}.png").write_bytes(base64.b64decode(encoded.partition(",")[2]))
        await browser.close()
    (args.output / "orbit.json").write_text(json.dumps({
        "input": "static/gallery/experiment6/3d/mesh.glb",
        "renderer": "Three.js Cycles-baked materials",
        "center": center, "distance": args.distance,
        "size": [args.width, args.height], "count": args.count,
        "hide_body": args.hide_body,
    }, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hide-body", action="store_true")
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--height", type=int, default=600)
    parser.add_argument("--count", type=int, default=180)
    parser.add_argument("--distance", type=float, default=2.757577774495903)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    handler = partial(SimpleHTTPRequestHandler, directory=str(SITE))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asyncio.run(render(args, server.server_port))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
