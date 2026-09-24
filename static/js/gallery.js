// Interactive viewer (Cycles lighting baked per texel) with the input photo and sewing pattern
// beside it and the layer buttons under it, plus the turntable wall that picks the result.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { bakedParts, setBaked } from './bakedmat.js?v=20260923r';

const $ = (s, r = document) => r.querySelector(s);
const REDUCED = matchMedia('(prefers-reduced-motion: reduce)').matches;
// negative = same turning direction as the Cycles turntables; ~20 s per turn
const ROTATE_SPEED = -1.5;
const RESUME_MS = 3500;            // idle time before auto-rotate resumes
const ELEV = THREE.MathUtils.degToRad(4);
const ease = t => 1 - Math.pow(1 - t, 3);
const layerOf = name => (/^l(\d+)/.exec(name) || [])[1];
// H.264 where available, VP9 for Chromium builds without it
const VIDEO_EXT = document.createElement('video').canPlayType('video/mp4; codecs="avc1.64001F"') ? '.mp4' : '.webm';
// every asset carries the site version, so a re-bake or re-render reaches browsers that cached the old one
const assetUrl = url => `${url}?v=${window.SITE_VERSION || ''}`;

class Stage {
  constructor(view) {
    this.view = view;
    this.canvas = $('#stage-canvas');
    const r = this.renderer = new THREE.WebGLRenderer({ canvas: this.canvas, antialias: true, powerPreference: 'high-performance' });
    // always at least 2x: on 1x screens this supersamples, which averages away the sub-pixel
    // seam specks that Cycles' many samples never show
    r.setPixelRatio(Math.max(2, Math.min(devicePixelRatio, 2)));
    r.outputColorSpace = THREE.SRGBColorSpace;
    r.toneMapping = THREE.NoToneMapping;      // colours are already display-referred
    r.setClearColor(0xf0f0f0, 1);           // CHORD's viewer gray
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.01, 60);
    const c = this.controls = new OrbitControls(this.camera, this.canvas);
    Object.assign(c, {
      enableDamping: true, dampingFactor: 0.085, enablePan: true, screenSpacePanning: true, rotateSpeed: 0.8, zoomSpeed: 0.9,
      autoRotate: !REDUCED, autoRotateSpeed: ROTATE_SPEED, minPolarAngle: 0.06, maxPolarAngle: Math.PI - 0.06,
    });
    this.wantRotate = !REDUCED;
    c.addEventListener('start', () => this.userStart());
    c.addEventListener('end', () => this.userEnd());
    this.gltf = new GLTFLoader();
    const draco = new DRACOLoader();
    draco.setDecoderPath('./static/js/vendor/three/addons/libs/draco/gltf/');
    this.gltf.setDRACOLoader(draco);
    this.texLoader = new THREE.TextureLoader();
    this.aniso = Math.min(8, r.capabilities.getMaxAnisotropy());
    this.small = matchMedia('(max-width: 768px)').matches || r.capabilities.maxTextureSize < 8192;
    this.model = null;
    this.token = 0;
    this.tween = null;
    this.showBody = true;
    this.onChange = () => {};
    new ResizeObserver(() => this.resize()).observe(view);
    this.inView = false;
    new IntersectionObserver(e => { this.inView = e[0].isIntersecting; this.run(); }, { threshold: 0.02 }).observe(view);
    document.addEventListener('visibilitychange', () => this.run());
    this.canvas.addEventListener('dblclick', () => this.resetView());
    this.canvas.addEventListener('contextmenu', e => e.preventDefault());
    this.resize();
  }

  run() {
    const on = this.inView && !document.hidden;
    this.renderer.setAnimationLoop(on ? () => this.frame() : null);
  }

  frame() {
    if (this.tween) this.stepTween();
    // ease auto-rotation in and out instead of snapping
    const target = this.wantRotate && !this.dragging ? ROTATE_SPEED : 0;
    this.controls.autoRotateSpeed += (target - this.controls.autoRotateSpeed) * 0.06;
    this.controls.autoRotate = Math.abs(this.controls.autoRotateSpeed) > 1e-3;
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  resize() {
    const w = this.view.clientWidth, h = this.view.clientHeight;
    if (!w || !h) return;
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    if (this.fit) this.fitLimits();
  }

  userStart() {
    this.dragging = true;
    this.tween = null;
    clearTimeout(this.resumeTimer);
  }

  userEnd() {
    // hold still for a moment after a drag, then the turntable picks up again
    clearTimeout(this.resumeTimer);
    this.resumeTimer = setTimeout(() => { this.dragging = false; }, RESUME_MS);
  }

  setRotate(on) {
    this.wantRotate = on;
    if (on) { clearTimeout(this.resumeTimer); this.dragging = false; }
  }

  // ---- loading ----
  loadTex(url, id) {
    // phones and small GPUs take the 2K skin
    if (this.small && url.endsWith('/body.webp')) url = url.replace(/body\.webp$/, 'body_m.webp');
    return new Promise((res, rej) => this.texLoader.load(assetUrl(url, id), t => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.flipY = false;                          // glTF UV convention
      t.anisotropy = this.aniso;
      res(t);
    }, undefined, rej));
  }

  // `ready` (the photo and pattern stills) is awaited too, so everything swaps in one frame
  async load(item, progress, ready = Promise.resolve()) {
    const token = ++this.token;
    const m = item.model;
    const base = m.dir;
    const state = m.states.length - 1;
    const urls = [];
    const st = m.states[state];
    for (const [name, t] of Object.entries(st.tex)) urls.push(...[].concat(t));
    let done = 0;
    const tick = () => progress(++done / (urls.length + 1));
    const [gltf, ...texs] = await Promise.all([
      this.gltf.loadAsync(assetUrl(base + m.mesh, item.id)).then(g => (tick(), g)),
      ...urls.map(u => this.loadTex(base + u, item.id).then(t => (tick(), t))),
    ]);
    await ready;
    if (token !== this.token) { texs.forEach(t => t.dispose()); return false; }
    const texMap = new Map(urls.map((u, i) => [u, texs[i]]));
    const root = gltf.scene;
    const meshes = {};
    root.traverse(o => { if (o.isMesh && !o.name.endsWith('_back')) meshes[o.name.toLowerCase()] = o; });
    const parts = [];
    for (const [name, mesh] of Object.entries(meshes)) {
      const garment = name !== 'body';
      const back = bakedParts(mesh, !garment);
      parts.push({ name, layer: garment ? +layerOf(name) : -1, mesh, back, garment });
    }
    const model = { item, root, parts, texCache: new Map([[state, texMap]]), state: -1 };
    this.applyState(model, state);
    texs.forEach(t => this.renderer.initTexture(t));
    this.swap(model);
    return true;
  }

  async setState(k) {
    const model = this.model;
    if (!model || k === model.state) return;
    if (!model.texCache.has(k)) {
      const st = model.item.model.states[k];
      const urls = Object.values(st.tex).flat();
      const texs = await Promise.all(urls.map(u => this.loadTex(model.item.model.dir + u, model.item.id)));
      model.texCache.set(k, new Map(urls.map((u, i) => [u, texs[i]])));
    }
    if (model !== this.model) return;
    this.applyState(model, k);
  }

  applyState(model, k) {
    const st = model.item.model.states[k];
    const tex = model.texCache.get(k);
    for (const p of model.parts) {
      const t = st.tex[p.name];
      const on = !!t && (p.layer < 0 ? this.showBody : true);
      p.mesh.visible = on;
      if (!t) continue;
      const [a, b] = [].concat(t);
      setBaked(p.mesh, p.back, tex.get(a), b && tex.get(b), !p.garment);
    }
    model.state = k;
    this.onChange(model);
  }

  setBody(on) {
    this.showBody = on;
    if (this.model) this.applyState(this.model, this.model.state);
  }

  swap(model) {
    const old = this.model;
    if (old) {
      this.scene.remove(old.root);
      old.root.traverse(o => { if (o.isMesh) { o.geometry.dispose(); o.material.dispose(); } });
      old.texCache.forEach(m => m.forEach(t => t.dispose()));
    }
    this.model = model;
    this.scene.add(model.root);
    this.frameModel(model);
  }

  // ---- framing ----
  frameModel(model) {
    model.root.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(model.root);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    // horizontal radius about the vertical axis, so every azimuth fits
    let r2 = 0;
    const v = new THREE.Vector3();
    model.root.traverse(o => {
      if (!o.isMesh || o.name.endsWith('_back')) return;
      const pos = o.geometry.attributes.position;
      for (let i = 0; i < pos.count; i += 3) {
        v.fromBufferAttribute(pos, i).applyMatrix4(o.matrixWorld);
        r2 = Math.max(r2, (v.x - center.x) ** 2 + (v.z - center.z) ** 2);
      }
    });
    this.fit = { center, height: size.y, radius: Math.sqrt(r2) };
    this.controls.target.copy(center);
    this.fitLimits();
    this.camera.near = this.fit.dist / 50;
    this.camera.far = this.fit.dist * 10;
    this.camera.updateProjectionMatrix();
    // enter with a short swing towards the front view
    this.placeAt(-0.55, ELEV + 0.05, this.fit.dist * 1.08);
    this.resetView(1100);
  }

  fitLimits() {
    const f = this.fit, cam = this.camera;
    const tv = Math.tan(THREE.MathUtils.degToRad(cam.fov) / 2), th = tv * cam.aspect;
    const dist = Math.max((f.height * 0.6) / tv, (f.radius * 1.1) / th) + f.radius * 0.45;
    f.dist = dist;
    this.controls.minDistance = dist * 0.28;
    this.controls.maxDistance = dist * 1.7;
  }

  placeAt(az, el, d) {
    const c = this.controls.target;
    this.camera.position.set(c.x + d * Math.cos(el) * Math.sin(az), c.y + d * Math.sin(el), c.z + d * Math.cos(el) * Math.cos(az));
    this.camera.lookAt(c);
  }

  resetView(ms = 900) {
    if (!this.fit) return;
    const off = this.camera.position.clone().sub(this.controls.target);
    const s = new THREE.Spherical().setFromVector3(off);
    // shortest way round to the front
    let az = s.theta % (2 * Math.PI);
    if (az > Math.PI) az -= 2 * Math.PI;
    if (az < -Math.PI) az += 2 * Math.PI;
    // a pan moves the target; the reset glides it back to the centre
    this.tween = { t0: performance.now(), ms, from: { az, el: Math.PI / 2 - s.phi, d: s.radius }, to: { az: 0, el: ELEV, d: this.fit.dist },
                   target: this.controls.target.clone() };
  }

  stepTween() {
    const tw = this.tween;
    const k = Math.min(1, (performance.now() - tw.t0) / tw.ms), e = ease(k);
    const lerp = key => tw.from[key] + (tw.to[key] - tw.from[key]) * e;
    this.controls.target.lerpVectors(tw.target, this.fit.center, e);
    this.placeAt(lerp('az'), lerp('el'), lerp('d'));
    if (k >= 1) this.tween = null;
  }
}

// ---------------------------------------------------------------------------
async function main() {
  const data = await (await fetch('./static/data/gallery.json?v=' + (window.SITE_VERSION || ''))).json();
  const items = data.items;
  const byId = new Map(items.map(it => [it.id, it]));
  const view = $('#stage-view');
  let stage = null;
  try { stage = new Stage(view); } catch (e) { console.warn('WebGL unavailable, showing turntables', e); }
  if (!stage) {
    // no WebGL: the stage plays the Cycles turntable instead
    const v = document.createElement('video');
    Object.assign(v, { muted: true, loop: true, autoplay: true, playsInline: true });
    v.className = 'stage__fallback';
    view.querySelector('canvas').replaceWith(v);
    view.classList.add('is-fallback');
    stage = {
      fallback: v, model: null, onChange() {}, resize() {},
      async load(it, progress, ready) {
        await ready;
        v.src = assetUrl(it.video.replace(/\.mp4$/, VIDEO_EXT), it.id);
        v.play().catch(() => {});
        this.model = { item: it, state: it.model.states.length - 1 };
        return true;
      },
      // no 3D to peel, but the pattern still follows the layer list
      setState(k) { if (this.model) { this.model.state = k; this.onChange(this.model); } },
      setRotate() {}, setBody() {}, resetView() {},
    };
  }
  const loading = $('#stage-loading'), ring = $('#stage-ring');
  let current = null, loadTimer = null;

  // ---- wall ----
  const grid = $('#gallery-grid');
  const cards = new Map();
  const vidObs = new IntersectionObserver(entries => {
    for (const e of entries) {
      const v = e.target;
      if (e.isIntersecting) {
        if (!v.src) { v.src = v.dataset.src; v.load(); }
        v.play().catch(() => {});
      } else v.pause();
    }
  }, { rootMargin: '120px 0px', threshold: 0.15 });

  items.forEach((it, i) => {
    const card = document.createElement('article');
    card.className = 'card';
    card.tabIndex = 0;
    card.style.animationDelay = `${Math.min(i, 12) * 35}ms`;
    card.setAttribute('aria-label', it.title);
    card.innerHTML = `
      <div class="card__media">
        <video muted loop playsinline preload="none" poster="${assetUrl(it.poster, it.id)}" data-src="${assetUrl(it.video.replace(/\.mp4$/, VIDEO_EXT), it.id)}"></video>
        <div class="card__photo"><img loading="lazy" src="${it.thumb}" alt=""></div>
        <span class="card__cta">View in 3D</span>
      </div>
`;
    card.addEventListener('click', () => select(it.id, true));
    card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(it.id, true); } });
    grid.appendChild(card);
    cards.set(it.id, card);
    vidObs.observe(card.querySelector('video'));
  });

  const order = items.map(it => it.id);

  // ---- photo and pattern beside the viewer, layer buttons under it ----
  const layers = $('#stage-layers'), pattern = $('#stage-pattern');
  const still = src => {
    const img = new Image();
    img.decoding = 'async';
    img.src = src;
    return img.decode().catch(() => {}).then(() => img);
  };
  const renderPlan = model => {
    const k = model.state;
    layers.querySelectorAll('button').forEach((b, i) => b.classList.toggle('is-primary', i === k));
    pattern.querySelectorAll('img').forEach((img, i) => img.classList.toggle('is-on', i === k));
  };
  stage.onChange = renderPlan;

  // swap in the photo, the layer buttons and the pattern stills of a loaded result
  function commitSide(it, photo, stills) {
    photo.id = 'stage-photo';
    photo.alt = 'Input photo';
    photo.classList.toggle('is-cutout', !!it.cutout);
    $('#stage-photo').replaceWith(photo);
    $('#stage-title').textContent = it.title;
    const peel = it.model.states.length > 1;
    const label = (p, i) => {
      const t = p.names.join(' + ');
      return (i ? '+ ' : '') + t[0].toUpperCase() + t.slice(1);
    };
    layers.replaceChildren(...it.plan.map((p, i) => {
      const b = document.createElement('button');
      b.className = 'button is-light comparison-scene-button' + (peel ? '' : ' is-static');
      b.textContent = label(p, i);
      if (peel) {
        b.title = i ? `Add layer ${i + 1}` : 'Innermost layer only';
        b.addEventListener('click', () => stage.setState(Math.min(i, it.model.states.length - 1)));
      }
      return b;
    }));
    stills.forEach((img, i) => { img.alt = i === stills.length - 1 ? 'Sewing pattern' : ''; });
    pattern.replaceChildren(...stills);
  }

  async function select(id, user) {
    const it = byId.get(id);
    if (!it || current === id) return;
    current = id;
    cards.forEach((c, k) => c.classList.toggle('is-current', k === id));
    if (user) {
      const r = $('#gallery-stage').getBoundingClientRect();
      if (r.top < 0 || r.bottom > innerHeight) $('#viewer').scrollIntoView({ behavior: REDUCED ? 'auto' : 'smooth', block: 'start' });
    }
    clearTimeout(loadTimer);
    ring.style.strokeDashoffset = 106.8;
    loadTimer = setTimeout(() => loading.classList.add('is-on'), 250);
    // the old result stays up until the new model, photo and patterns are all ready
    const side = Promise.all([still(it.photo), Promise.all(it.pattern.map(still))]);
    const ok = await stage.load(it, p => { ring.style.strokeDashoffset = 106.8 * (1 - p); }, side)
      .catch(e => { console.error(e); return false; });
    if (!ok || current !== id) return;
    const [photo, stills] = await side;
    commitSide(it, photo, stills);
    renderPlan(stage.model || { state: it.model.states.length - 1 });
    clearTimeout(loadTimer);
    loading.classList.remove('is-on');
  }

  // ---- tools ----
  const tRot = $('#tool-rotate'), tBody = $('#tool-body');
  tRot.setAttribute('aria-pressed', String(!REDUCED));
  const toggleRotate = () => { const on = tRot.getAttribute('aria-pressed') !== 'true'; tRot.setAttribute('aria-pressed', String(on)); stage.setRotate(on); };
  const toggleBody = () => { const on = tBody.getAttribute('aria-pressed') !== 'true'; tBody.setAttribute('aria-pressed', String(on)); stage.setBody(on); };
  const full = () => {
    const el = view;
    if (document.fullscreenElement) document.exitFullscreen();
    else (el.requestFullscreen || el.webkitRequestFullscreen)?.call(el);
  };
  const step = d => {
    const i = order.indexOf(current);
    const next = order[(i + d + order.length) % order.length] || order[0];
    select(next, false);
  };
  tRot.addEventListener('click', toggleRotate);
  tBody.addEventListener('click', toggleBody);
  $('#tool-reset').addEventListener('click', () => stage.resetView());
  $('#tool-full').addEventListener('click', full);
  $('#stage-prev').addEventListener('click', () => step(-1));
  $('#stage-next').addEventListener('click', () => step(1));
  view.addEventListener('keydown', e => {
    const k = e.key.toLowerCase();
    if (k === 'arrowleft') step(-1);
    else if (k === 'arrowright') step(1);
    else if (k === ' ') toggleRotate();
    else if (k === 'b') toggleBody();
    else if (k === 'r') stage.resetView();
    else if (k === 'f') full();
    else return;
    e.preventDefault();
  });
  document.addEventListener('fullscreenchange', () => setTimeout(() => stage.resize(), 50));

  const hash = decodeURIComponent(location.hash.slice(1));
  select(byId.has(hash) ? hash : byId.has(data.default) ? data.default : items[0].id, false);
  if (byId.has(hash)) setTimeout(() => $('#viewer').scrollIntoView({ block: 'start' }), 300);
}

main();
