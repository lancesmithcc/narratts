# DESIGN.md — Qwen3 TTS Studio

## Theme
Dark. Scene: one person in a dim home studio at night, listening critically to generated audio on an M4 Max. Screen must not glare; audio waveform and accent glow carry the light. Warm dark, not blue-black.

## Color — strategy: Committed (warm ember accent carries identity)
OKLCH only. Neutrals tinted toward the accent hue (~75).

| Token | Value | Use |
|---|---|---|
| --bg | oklch(0.155 0.008 75) | page background |
| --bg-deep | oklch(0.125 0.007 75) | canvas wells, code blocks |
| --surface | oklch(0.195 0.010 75) | panels, inputs |
| --raised | oklch(0.24 0.012 75) | hover surfaces, chips |
| --line | oklch(0.30 0.014 75) | hairline borders |
| --text | oklch(0.93 0.006 85) | primary text |
| --muted | oklch(0.60 0.018 78) | secondary text |
| --faint | oklch(0.44 0.015 78) | tertiary, placeholders |
| --accent | oklch(0.78 0.145 72) | primary actions, live waveform, focus |
| --accent-hot | oklch(0.85 0.16 80) | hover/active accent |
| --accent-dim | oklch(0.34 0.06 70) | accent tints, selection bg |
| --ok | oklch(0.75 0.12 150) | success |
| --err | oklch(0.68 0.15 25) | errors |

No #000/#fff. No gradient text. No side-stripe borders. No glassmorphism.

## Typography
Space Grotesk only, weights 300 and 700 (nothing between). Display/headings 700, tight tracking (-0.02em to -0.04em). Body and UI 300. Scale ratio ≥1.3. Mono for code: ui-monospace stack. Body max 70ch.

## Layout
Single page, top bar (wordmark, model/health status, API-key control) + left rail nav (Generate, Clone, Voices, Docs). Content column max ~860px for forms, wider for docs tables. Spacing rhythm varies: hero section breathes (96px+), form clusters tight (12–16px).

## Motion
Signature: canvas particle swarm that idles as a slow-breathing waveform line, repels/attracts around the pointer, bursts on click/tap, drifts with scroll velocity, and during playback dances to a WebAudio analyser. Exponential ease-out everywhere (cubic-bezier(0.16,1,0.3,1)), 150–400ms. Respect prefers-reduced-motion: static waveform, no swarm.

## Components
- Buttons: 700 weight, accent fill for the ONE primary per view; others hairline ghost.
- Inputs: --surface fill, 1px --line border, accent focus ring (2px, offset 0).
- Tabs/rail items: 300 weight, active = 700 + accent text, no pill backgrounds.
- Audio result: inline player row with waveform, duration, model, download.
- Docs: endpoint rows with method chip (700, accent for POST, muted for GET), expandable curl examples in --bg-deep code blocks.
