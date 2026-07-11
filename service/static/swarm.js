/* Swarm — signature bar waveform, same visual language as the logo mark.
   Rounded vertical bars breathe as a wave, part around the pointer,
   ripple on click/tap, drift with scroll, and dance to live audio
   via an AnalyserNode during playback. */
(function () {
  "use strict";

  const canvas = document.getElementById("swarm");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ctx = canvas.getContext("2d");

  let W = 0, H = 0, dpr = 1;
  let particles = [];
  const N = innerWidth < 768 ? 64 : 120;
  const BAR_W = 3.5;

  // Interaction state
  const pointer = { x: -9999, y: -9999, vx: 0, vy: 0 };
  let scrollVel = 0, lastScrollY = scrollY;
  const pulses = []; // click bursts: {x, y, r, life}

  // Audio reactivity
  let analyser = null;
  let freq = null;
  let energy = 0; // smoothed 0..1
  let lastErr = null;

  const ACCENT = { h: 42, s: 78, l: 63 }; // warm ember in hsl-ish space for canvas

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    W = innerWidth; H = innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  }

  function baseline() { return H * 0.42; }

  function seed() {
    particles = [];
    for (let i = 0; i < N; i++) {
      const t = i / (N - 1);
      particles.push({
        t,                      // 0..1 position along the wave
        x: t * W,
        y: baseline(),
        vx: 0, vy: 0, h: 8,
        size: 0.8 + Math.pow((i * 7919) % 100 / 100, 2) * 2.2,
        phase: ((i * 104729) % 628) / 100,
        drift: 0.4 + ((i * 31) % 100) / 160,
      });
    }
  }

  function waveY(t, time) {
    // Layered sines make an organic idle waveform; audio energy amplifies it.
    const amp = (10 + energy * 90) * (0.35 + 0.65 * Math.sin(t * Math.PI));
    let y = Math.sin(t * 11 + time * 0.9) * amp * 0.55
          + Math.sin(t * 23 - time * 1.7) * amp * 0.3
          + Math.sin(t * 5 + time * 0.4) * amp * 0.45;
    if (freq) {
      // Map particle position onto the frequency spectrum.
      const bin = Math.min(freq.length - 1, Math.floor(t * freq.length * 0.7));
      y -= (freq[bin] / 255) * 70 * Math.sin(t * Math.PI);
    }
    return baseline() + y;
  }

  let frames = 0;

  function step(time) {
    frames++;
    try {
      stepInner(time);
    } catch (e) {
      lastErr = String(e);
    }
    requestAnimationFrame(step);
  }

  function stepInner(time) {
    ctx.clearRect(0, 0, W, H);
    const t = time / 1000;

    // Decay interaction forces
    scrollVel *= 0.92;
    energy *= 0.96;
    if (analyser && freq) {
      analyser.getByteFrequencyData(freq);
      let sum = 0;
      for (let i = 0; i < 32; i++) sum += freq[i];
      energy = Math.max(energy, Math.min(1, sum / (32 * 200)));
    }

    // Pulses expand and fade
    for (let i = pulses.length - 1; i >= 0; i--) {
      const p = pulses[i];
      p.r += 9;
      p.life -= 0.022;
      if (p.life <= 0) pulses.splice(i, 1);
    }

    const glow = 0.5 + energy * 0.5;

    for (const p of particles) {
      const targetX = p.t * W;
      const targetY = waveY(p.t, t) + Math.sin(t * p.drift + p.phase) * 4 + scrollVel * 30 * p.drift;

      // Bars stay anchored to the wave; springs keep the motion fluid.
      p.vx += (targetX - p.x) * 0.04;
      p.vy += (targetY - p.y) * 0.05;
      p.vx *= 0.82;
      p.vy *= 0.82;
      p.x += p.vx;
      p.y += p.vy;

      // Pointer = volume. Bars swell under the cursor with a smooth
      // gaussian falloff, like turning the level up on that band.
      const dx = p.x - pointer.x;
      const dy = p.y - pointer.y;
      const hoverBoost = 110 * Math.exp(-(dx * dx) / (2 * 90 * 90))
                             * Math.exp(-(dy * dy) / (2 * 170 * 170));

      // Click pulses ride outward along the wave as a swell, not a scatter.
      let pulseBoost = 0;
      for (const q of pulses) {
        const band = Math.abs(Math.abs(p.x - q.x) - q.r);
        if (band < 70) pulseBoost += (1 - band / 70) * q.life * 90;
      }

      // Smooth the height so swells rise and settle like real level meters.
      const amp = Math.abs(waveY(p.t, t) - baseline());
      const targetH = Math.max(
        BAR_W,
        8 + amp * 1.7
          + hoverBoost + pulseBoost
          + energy * 46 * (0.4 + 0.6 * Math.sin(p.t * Math.PI)),
      );
      p.h += (targetH - (p.h || targetH)) * 0.18;

      const lift = Math.min(1, (p.h - 8) / 130);
      const a = 0.14 + lift * 0.5 + energy * 0.3;
      const l = ACCENT.l + lift * 16 + energy * 12;

      ctx.beginPath();
      ctx.roundRect(p.x - BAR_W / 2, p.y - p.h / 2, BAR_W, p.h, BAR_W / 2);
      ctx.fillStyle = `hsla(${ACCENT.h}, ${ACCENT.s}%, ${l}%, ${a * glow})`;
      ctx.fill();
    }
  }

  function drawStatic() {
    // Reduced motion: calm static bars, no animation loop.
    resize();
    ctx.clearRect(0, 0, W, H);
    const bars = 80;
    for (let i = 0; i < bars; i++) {
      const t = i / (bars - 1);
      const h = Math.max(BAR_W, (10 + Math.abs(Math.sin(t * 9)) * 44) * Math.sin(t * Math.PI));
      ctx.beginPath();
      ctx.roundRect(t * (W - BAR_W), baseline() - h / 2, BAR_W, h, BAR_W / 2);
      ctx.fillStyle = `hsla(${ACCENT.h}, ${ACCENT.s}%, ${ACCENT.l}%, 0.16)`;
      ctx.fill();
    }
  }

  // ── Public API ────────────────────────────────────────
  window.Swarm = {
    version: 5,
    debug() {
      return { n: particles.length, W, H, sample: particles[10] ? { ...particles[10] } : null, lastErr };
    },
    pulse(x, y) {
      if (reduced) return;
      pulses.push({ x: x ?? W / 2, y: y ?? baseline(), r: 6, life: 1 });
      if (pulses.length > 6) pulses.shift();
    },
    attachAnalyser(node) {
      analyser = node;
      freq = new Uint8Array(node.frequencyBinCount);
    },
    detachAnalyser() {
      analyser = null;
      freq = null;
    },
    kick(strength) {
      energy = Math.min(1, Math.max(energy, strength ?? 0.6));
    },
  };

  if (reduced) {
    drawStatic();
    addEventListener("resize", drawStatic);
    return;
  }

  addEventListener("resize", resize);
  addEventListener("pointermove", (e) => { pointer.x = e.clientX; pointer.y = e.clientY; }, { passive: true });
  addEventListener("pointerleave", () => { pointer.x = -9999; pointer.y = -9999; });
  addEventListener("pointerdown", (e) => window.Swarm.pulse(e.clientX, e.clientY), { passive: true });
  addEventListener("scroll", () => {
    scrollVel = Math.max(-1, Math.min(1, (scrollY - lastScrollY) / 60));
    lastScrollY = scrollY;
  }, { passive: true });

  resize();
  requestAnimationFrame(step);
  // Some embedded/hidden contexts never deliver rAF; fall back to a timer
  // so the wave still lives wherever the page renders.
  setTimeout(() => {
    if (frames === 0) {
      setInterval(() => {
        try { stepInner(performance.now()); } catch (e) { lastErr = String(e); }
      }, 33);
    }
  }, 800);
})();
