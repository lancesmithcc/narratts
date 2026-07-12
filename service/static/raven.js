import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const canvas = document.getElementById("raven-canvas");
const stage = document.getElementById("raven-stage");
const label = document.getElementById("raven-status");
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

if (!canvas || !stage) throw new Error("Narra raven mount missing");

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 50);
camera.position.set(0, 0.04, 3.5);

// Separate rigs let a static authored mesh turn and dance without deforming it.
const turnRig = new THREE.Group();
const danceRig = new THREE.Group();
turnRig.add(danceRig);
scene.add(turnRig);

const keyLight = new THREE.DirectionalLight(0xffdfb0, 2.55);
keyLight.position.set(-3, 4, 5);
scene.add(keyLight);
const warmRim = new THREE.DirectionalLight(0xf0b352, 1.32);
warmRim.position.set(4, 2, -4);
scene.add(warmRim);
const emberRim = new THREE.DirectionalLight(0xffc76b, 0.75);
emberRim.position.set(-3, 0, 3);
scene.add(emberRim);
scene.add(new THREE.HemisphereLight(0xd8c3a1, 0x15110d, 1.15));

const groundGlow = new THREE.Mesh(
  new THREE.CircleGeometry(0.42, 32),
  new THREE.MeshBasicMaterial({ color: 0xf0a13c, transparent: true, opacity: 0.08, depthWrite: false }),
);
groundGlow.scale.set(1.5, 0.34, 1);
groundGlow.position.set(0, -0.42, -0.05);
scene.add(groundGlow);

const pointer = new THREE.Vector2();
const stateLabels = {
  loading: "perching",
  idle: "listening",
  thinking: "weaving voice",
  playing: "speaking",
  recording: "recording",
};

let model = null;
let wingPosBone = null;
let wingNegBone = null;
let lowerBeakBone = null;
const boneRest = {};
let state = "loading";
let reactionKind = "idle";
let impulse = 0;
let danceAge = 99;
let dancingVisible = false;
let analyser = null;
let spectrum = null;
let audioEnergy = 0;
let lastTime = 0;
let cawAge = 99;
let cawDuration = 1.4;
let cawVisible = false;
let nextCawAt = 24;
let cawIntervalIndex = 0;

const cawIntervals = [37, 52, 43, 61, 34, 48];

function setState(next, statusText) {
  state = next || "idle";
  stage.dataset.state = state;
  label.textContent = statusText || stateLabels[state] || state;
}

function react(kind = "hello", strength = 0.7) {
  reactionKind = kind;
  impulse = Math.min(1, Math.max(impulse, strength));
  if (kind === "click" || kind === "success") danceAge = 0;
}

function attachAnalyser(node) {
  analyser = node;
  spectrum = new Uint8Array(node.frequencyBinCount);
  setState("playing");
}

function detachAnalyser() {
  analyser = null;
  spectrum = null;
  audioEnergy = 0;
  if (state === "playing") setState("idle");
}

function triggerCaw() {
  if (state !== "idle") return false;
  cawAge = 0;
  return true;
}

window.NarraRaven = { setState, react, attachAnalyser, detachAnalyser, caw: triggerCaw };
setState("loading");

stage.addEventListener("pointerenter", () => react("hello", 0.42));
stage.addEventListener("click", () => react("click", 1));
stage.addEventListener("dblclick", () => {
  danceAge = 99;
  triggerCaw();
});
addEventListener("pointermove", (event) => {
  pointer.x = (event.clientX / innerWidth) * 2 - 1;
  pointer.y = -(event.clientY / innerHeight) * 2 + 1;
}, { passive: true });

function fitModel() {
  if (!model) return;
  model.position.set(0, 0, 0);
  const box = new THREE.Box3().setFromObject(model);
  const center = box.getCenter(new THREE.Vector3());
  const size = box.getSize(new THREE.Vector3());
  model.position.sub(center);
  model.position.y += 0.02;
  const vertical = size.y / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
  const horizontal = size.x / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect);
  camera.position.set(0, 0.03, Math.max(vertical, horizontal) * 1.1);
  camera.lookAt(0, 0.03, 0);
  camera.updateProjectionMatrix();
  groundGlow.position.y = -size.y * 0.5 + 0.01;
  groundGlow.scale.set(size.x * 0.85, size.x * 0.2, 1);
}

function resize() {
  const rect = stage.getBoundingClientRect();
  const width = Math.max(1, rect.width);
  const height = Math.max(1, rect.height);
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  fitModel();
  if (reduced && model) renderer.render(scene, camera);
}

new ResizeObserver(resize).observe(stage);
resize();

new GLTFLoader().load(
  "assets/raven-rigged.glb?v=2",
  (gltf) => {
    model = gltf.scene;
    if (!model.getObjectByName("NarraRaven")) throw new Error("NarraRaven missing from raven-rigged.glb");
    danceRig.add(model);
    wingPosBone = model.getObjectByName("Wing_PosZ");
    wingNegBone = model.getObjectByName("Wing_NegZ");
    lowerBeakBone = model.getObjectByName("LowerBeak");
    for (const [name, bone] of [["wingPos", wingPosBone], ["wingNeg", wingNegBone], ["beak", lowerBeakBone]]) {
      if (bone) boneRest[name] = bone.rotation.clone();
    }
    model.traverse((child) => {
      if (!child.isMesh) return;
      child.castShadow = false;
      child.receiveShadow = false;
      if (child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        const animatedMaterials = materials.map((sourceMaterial) => {
          const material = sourceMaterial.clone();
          material.needsUpdate = true;
          material.roughness = Math.max(0.5, material.roughness ?? 0.7);
          return material;
        });
        child.material = Array.isArray(child.material) ? animatedMaterials : animatedMaterials[0];
      }
    });
    fitModel();
    setState("idle");
    react("hello", 0.55);
    renderer.render(scene, camera);
  },
  undefined,
  (error) => {
    setState("idle", "raven offline");
    console.error("Could not load raven.glb mascot", error);
  },
);

function render(timeMs) {
  const time = timeMs / 1000;
  const dt = Math.min(0.05, time - lastTime || 0.016);
  lastTime = time;

  if (analyser && spectrum) {
    analyser.getByteFrequencyData(spectrum);
    let sum = 0;
    for (let i = 0; i < Math.min(32, spectrum.length); i++) sum += spectrum[i];
    audioEnergy += (Math.min(1, sum / (32 * 175)) - audioEnergy) * 0.28;
  } else {
    audioEnergy *= 0.9;
  }

  impulse = Math.max(0, impulse - dt * 1.25);
  danceAge += dt;
  cawAge += dt;
  const thinking = state === "thinking" ? 1 : 0;
  const recording = state === "recording" ? 1 : 0;
  const activity = Math.max(audioEnergy, thinking * 0.42, recording * 0.6);
  const breath = Math.sin(time * 1.8);

  // Faces user most of the time, with brief attentive glances both ways.
  const glancePhase = time % 22;
  const glanceLeft = glancePhase >= 5.5 && glancePhase <= 8.5
    ? Math.sin(((glancePhase - 5.5) / 3) * Math.PI) * 0.38 : 0;
  const glanceRight = glancePhase >= 13 && glancePhase <= 16
    ? Math.sin(((glancePhase - 13) / 3) * Math.PI) * -0.34 : 0;
  const attentiveTurn = Math.PI / 2 + glanceLeft + glanceRight;

  // Autonomous dance every 20s plus immediate click/success choreography.
  const autoDanceT = THREE.MathUtils.clamp(((time % 20) - 15) / 4, 0, 1);
  const autoDance = autoDanceT > 0 && autoDanceT < 1 ? Math.sin(autoDanceT * Math.PI) ** 2 : 0;
  const clickDanceT = THREE.MathUtils.clamp(danceAge / 3.2, 0, 1);
  const clickDance = danceAge < 3.2 ? Math.sin(clickDanceT * Math.PI) ** 2 : 0;
  const dance = Math.max(autoDance, clickDance);
  const danceProgress = clickDance > autoDance ? clickDanceT : autoDanceT;
  const danceSpin = THREE.MathUtils.smoothstep(danceProgress, 0, 1) * Math.PI * 2;
  const beat = Math.sin(time * 9.5);
  const halfBeat = Math.sin(time * 4.75);

  if (time >= nextCawAt) {
    nextCawAt = time + cawIntervals[cawIntervalIndex++ % cawIntervals.length];
    if (document.visibilityState === "visible" && state === "idle" && audioEnergy < 0.04) triggerCaw();
  }

  const cawPulse = (start, duration) => {
    const value = THREE.MathUtils.clamp((cawAge - start) / duration, 0, 1);
    return cawAge >= start && cawAge <= start + duration ? Math.sin(value * Math.PI) ** 1.35 : 0;
  };
  const firstCaw = cawPulse(0.02, 0.6);
  const secondCaw = cawPulse(0.8, 0.58);
  const cawFlap = Math.max(firstCaw, secondCaw);
  const spreadRelease = Math.max(0.18, cawDuration - 0.32);
  const cawSpread = cawAge < 0.2
    ? THREE.MathUtils.smoothstep(cawAge, 0, 0.2)
    : cawAge < spreadRelease
      ? 1
      : cawAge < cawDuration
        ? 1 - THREE.MathUtils.smoothstep(cawAge, spreadRelease, cawDuration)
        : 0;
  const idleWingPhase = (time % 11 - 7.6) / 1.5;
  const idleWingStretch = idleWingPhase >= 0 && idleWingPhase <= 1
    ? Math.sin(idleWingPhase * Math.PI) ** 2 * 0.22 : 0;
  const beakOpen = Math.max(
    firstCaw * (0.55 + Math.abs(Math.sin(cawAge * 19)) * 0.45),
    secondCaw * (0.55 + Math.abs(Math.sin(cawAge * 21)) * 0.45),
  );
  const wingMotion = Math.min(1, cawSpread + dance * (0.25 + Math.abs(beat) * 0.14) + idleWingStretch + activity * 0.07);
  if (wingPosBone && boneRest.wingPos) {
    wingPosBone.rotation.x = boneRest.wingPos.x + wingMotion * 0.72;
    wingPosBone.rotation.y = boneRest.wingPos.y + wingMotion * 0.12;
    wingPosBone.rotation.z = boneRest.wingPos.z - wingMotion * 0.26;
  }
  if (wingNegBone && boneRest.wingNeg) {
    wingNegBone.rotation.x = boneRest.wingNeg.x - wingMotion * 0.72;
    wingNegBone.rotation.y = boneRest.wingNeg.y - wingMotion * 0.12;
    wingNegBone.rotation.z = boneRest.wingNeg.z + wingMotion * 0.26;
  }
  if (lowerBeakBone && boneRest.beak) lowerBeakBone.rotation.z = boneRest.beak.z + beakOpen * 0.34;

  const hopPhase = Math.max(0, Math.sin((1 - impulse) * Math.PI));
  const hop = reactionKind === "click" ? hopPhase * impulse * 0.09 : 0;
  const targetTurn = cawAge < cawDuration ? Math.PI / 2 : attentiveTurn + danceSpin + pointer.x * 0.1;
  turnRig.rotation.y += (targetTurn - turnRig.rotation.y) * (dance > 0.05 ? 0.2 : 0.06);

  danceRig.position.x = halfBeat * dance * 0.065;
  danceRig.position.y = breath * 0.008 + hop + cawFlap * 0.035 + Math.abs(beat) * dance * 0.065 + Math.sin(time * 11) * audioEnergy * 0.02;
  danceRig.rotation.x = pointer.y * 0.035 + recording * Math.sin(time * 5) * 0.04 + cawFlap * Math.sin(cawAge * 12) * 0.045 + dance * Math.sin(time * 7) * 0.08;
  danceRig.rotation.z = breath * 0.008 + beat * dance * 0.11 + cawFlap * Math.sin(cawAge * 10) * 0.055 + activity * Math.sin(time * 8) * 0.055;
  danceRig.scale.x = 1 - Math.abs(beat) * dance * 0.035 + cawFlap * 0.035 + activity * 0.018;
  danceRig.scale.y = 1 + breath * 0.008 + Math.abs(beat) * dance * 0.055 + cawFlap * 0.025 + activity * 0.035;
  danceRig.scale.z = 1 + Math.abs(halfBeat) * dance * 0.025 + cawFlap * 0.08 + cawSpread * 0.22;

  groundGlow.material.opacity = 0.07 + activity * 0.12 + dance * 0.08;
  groundGlow.scale.y = 0.16 + (1 - danceRig.position.y * 1.8) * 0.04;

  const shouldShowDance = dance > 0.08 && state === "idle";
  const shouldShowCaw = cawAge < cawDuration && state === "idle";
  dancingVisible = shouldShowDance;
  cawVisible = shouldShowCaw;
  const motionLabel = shouldShowCaw ? "caw caw" : shouldShowDance ? "dancing" : stateLabels[state] || state;
  if (label.textContent !== motionLabel) label.textContent = motionLabel;

  renderer.render(scene, camera);
  if (!reduced) requestAnimationFrame(render);
}

if (!reduced) requestAnimationFrame(render);
