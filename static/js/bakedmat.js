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
// Only the body's back side is pushed back: it is a closed surface, so its back faces meet
// the front ones along every silhouette. Cloth layers lie millimetres apart (a lapel on its
// jacket), and pushing their back faces back would let the covered layer show through.
export function bakedParts(mesh, isBody) {
  mesh.material = new THREE.MeshBasicMaterial({ side: THREE.FrontSide });
  const back = new THREE.Mesh(mesh.geometry, new THREE.ShaderMaterial({
    uniforms: { outer: { value: DARK }, inner: { value: DARK }, fade: { value: new THREE.Vector2(0.12, 0.42) } },
    vertexShader: vert,
    fragmentShader: frag,
    side: THREE.BackSide,
    polygonOffset: !!isBody,
    polygonOffsetFactor: isBody ? 4 : 0,
    polygonOffsetUnits: isBody ? 8 : 0,
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
