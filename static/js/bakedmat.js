// Cycles-baked surfaces: every texture already holds the final display colour.
// Both sides render, as in Cycles. The front side shows its bake, the back side the inner
// bake made with flipped normals (an open mouth reads black, an eye socket keeps its soft
// shading, as in the turntables).
import * as THREE from 'three';

const vert = /* glsl */`
  varying vec2 vUv;
  varying vec3 vView;
  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = mv.xyz;
    gl_Position = projectionMatrix * mv;
  }`;

// a back face seen edge-on (a fold at the silhouette) fades to the front bake,
// which is what Cycles shows there
const frag = /* glsl */`
  uniform sampler2D outer;
  uniform sampler2D inner;
  uniform vec2 fade;
  varying vec2 vUv;
  varying vec3 vView;
  void main() {
    vec3 n = normalize(cross(dFdx(vView), dFdy(vView)));
    float facing = abs(dot(n, normalize(-vView)));
    vec3 c = mix(texture2D(outer, vUv).rgb, texture2D(inner, vUv).rgb, smoothstep(fade.x, fade.y, facing));
    gl_FragColor = vec4(c, 1.0);
    #include <colorspace_fragment>
  }`;

// inside of the body: the Cycles turntables show it at about sRGB (4, 1, 0)
const DARK = new THREE.DataTexture(new Uint8Array([4, 2, 1, 255]), 1, 1);
DARK.colorSpace = THREE.SRGBColorSpace;
DARK.needsUpdate = true;

// front material on the mesh itself, back side as a child sharing its geometry.
// The body's front gets the smallest push, so skin that grazes snug cloth along a seam does
// not dot the seam (Cycles' many samples average it away); its back side goes much further,
// since it is a closed surface whose back faces meet the front ones along every silhouette.
// Cloth back faces get a small constant push (no slope term), which keeps the dark inside
// from flickering through seam creases: cloth layers lie millimetres apart (a lapel on its
// jacket), and a slope-scaled push would let the covered layer show through at grazing angles.
export function bakedParts(mesh, isBody) {
  mesh.material = new THREE.MeshBasicMaterial({
    side: THREE.FrontSide, polygonOffset: !!isBody, polygonOffsetFactor: isBody ? 1 : 0, polygonOffsetUnits: isBody ? 1 : 0,
  });
  const back = new THREE.Mesh(mesh.geometry, new THREE.ShaderMaterial({
    uniforms: { outer: { value: DARK }, inner: { value: DARK }, fade: { value: new THREE.Vector2(0.12, 0.42) } },
    vertexShader: vert,
    fragmentShader: frag,
    side: THREE.BackSide,
    polygonOffset: true,
    polygonOffsetFactor: isBody ? 32 : 1,
    polygonOffsetUnits: 64,
  }));
  back.name = mesh.name + '_back';
  mesh.add(back);
  return back;
}

// back side: the inner bake (Cycles shades back faces with the flipped normal);
// a body without one falls back to its dark inside
export function setBaked(mesh, back, outer, inner, isBody) {
  mesh.material.map = outer;
  mesh.material.needsUpdate = true;
  const u = back.material.uniforms;
  u.outer.value = outer;
  u.inner.value = isBody ? (inner || DARK) : (inner || outer);
  if (isBody) u.fade.value.set(0, 1e-3); else u.fade.value.set(0.12, 0.42);
}
