// Materials for Cycles-baked surfaces: the texture already holds the final display colour.
import * as THREE from 'three';

// Cloth seen from inside shows its inner bake. Where a back face is seen at a grazing
// angle (a fold at the silhouette), the inner bake is not what Cycles sees there, so it
// fades to the outer bake.
const vert = /* glsl */`
  varying vec2 vUv;
  varying vec3 vView;
  void main() {
    vUv = uv;
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    vView = mv.xyz;
    gl_Position = projectionMatrix * mv;
  }`;

const frag = /* glsl */`
  uniform sampler2D outer;
  uniform sampler2D inner;
  uniform float useInner;
  varying vec2 vUv;
  varying vec3 vView;
  void main() {
    vec3 a = texture2D(outer, vUv).rgb;
    vec3 c = a;
    if (!gl_FrontFacing && useInner > 0.5) {
      vec3 n = normalize(cross(dFdx(vView), dFdy(vView)));
      float facing = abs(dot(n, normalize(-vView)));
      c = mix(a, texture2D(inner, vUv).rgb, smoothstep(0.12, 0.42, facing));
    }
    gl_FragColor = vec4(c, 1.0);
    #include <colorspace_fragment>
  }`;

export function clothMaterial() {
  return new THREE.ShaderMaterial({
    uniforms: { outer: { value: null }, inner: { value: null }, useInner: { value: 1 } },
    vertexShader: vert,
    fragmentShader: frag,
    side: THREE.DoubleSide,
  });
}

export function setCloth(mat, outer, inner) {
  mat.uniforms.outer.value = outer;
  mat.uniforms.inner.value = inner || outer;
  mat.uniforms.useInner.value = inner ? 1 : 0;
}

export function skinMaterial() {
  return new THREE.MeshBasicMaterial({ side: THREE.FrontSide });
}
