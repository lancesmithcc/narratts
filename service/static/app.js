/* Qwen3 TTS Studio — frontend logic. Talks to the FastAPI service on the same origin. */
(function () {
  "use strict";

  const $ = (sel, el = document) => el.querySelector(sel);
  const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

  // ── State ─────────────────────────────────────────────
  const KEY_STORAGE = "tts-api-key";
  let apiKey = localStorage.getItem(KEY_STORAGE) || "";
  let voices = [];
  let pickedVoiceIds = new Set();   // clone view selection
  let genPickedIds = new Set();     // generate view "My voices" selection
  let pendingFile = null;

  const LANGUAGES = ["Auto", "English", "Chinese", "French", "German", "Italian",
    "Japanese", "Korean", "Portuguese", "Russian", "Spanish"];

  const LOADING_LINES = [
    "Sculpting the frequencies…",
    "Weaving the audio…",
    "Brewing the perfect tone…",
    "Warming up the vocal cords…",
  ];

  const DESIGN_EXAMPLES = [
    "A weathered sea captain, slow and salty",
    "A weary noir detective, gravelly and low",
    "A frantic news anchor, rapid-fire and breathless",
    "A serene monk, ethereal and rhythmic",
  ];

  // ── Audio plumbing ────────────────────────────────────
  let audioCtx = null;
  let current = null; // { el, btn, canvas, analyserSrc }

  function ensureCtx() {
    if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    if (audioCtx.state === "suspended") audioCtx.resume();
    return audioCtx;
  }

  function stopCurrent() {
    if (!current) return;
    current.el.pause();
    current.btn.classList.remove("playing");
    current.btn.textContent = "▶";
    window.Swarm.detachAnalyser();
    window.NarraRaven?.detachAnalyser();
    current = null;
  }

  function playThroughSwarm(el, btn) {
    const ctx = ensureCtx();
    if (!el._srcNode) {
      el._srcNode = ctx.createMediaElementSource(el);
      el._analyser = ctx.createAnalyser();
      el._analyser.fftSize = 256;
      el._srcNode.connect(el._analyser);
      el._analyser.connect(ctx.destination);
    }
    window.Swarm.attachAnalyser(el._analyser);
    window.NarraRaven?.attachAnalyser(el._analyser);
    el.play();
    btn.classList.add("playing");
    btn.textContent = "❚❚";
    current = { el, btn };
    el.onended = () => { if (current && current.el === el) stopCurrent(); };
  }

  function togglePlay(el, btn) {
    if (current && current.el === el && !el.paused) { stopCurrent(); return; }
    stopCurrent();
    playThroughSwarm(el, btn);
  }

  // ── API client ────────────────────────────────────────
  async function api(path, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;
    if (opts.json) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    const res = await fetch(path, Object.assign({}, opts, { headers }));
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || j.error || detail;
      } catch (_) { /* keep statusText */ }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  // ── Toast ─────────────────────────────────────────────
  let toastTimer = null;
  function toast(msg, isErr = false) {
    const el = $("#toast");
    el.textContent = msg;
    el.classList.toggle("err", isErr);
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3200);
  }

  // ── Health ────────────────────────────────────────────
  async function pollHealth() {
    const dot = $("#status-dot"), text = $("#status-text");
    try {
      const h = await api("/health");
      if (h.status === "ok") {
        dot.className = "status-dot ok";
        text.textContent = `${h.loaded_model} · ${h.device}`;
      } else {
        dot.className = "status-dot loading";
        text.textContent = "warming model…";
      }
    } catch (e) {
      dot.className = "status-dot err";
      text.textContent = /Invalid API key|Bearer/.test(e.message) ? "bad API key" : "offline";
    }
  }

  // ── Navigation ────────────────────────────────────────
  $$(".rail-item").forEach((btn) => {
    btn.addEventListener("click", () => {
      $$(".rail-item").forEach((b) => b.classList.remove("active"));
      $$(".view").forEach((v) => v.classList.remove("active"));
      btn.classList.add("active");
      $(`#view-${btn.dataset.view}`).classList.add("active");
      window.Swarm.kick(0.35);
      window.NarraRaven?.react("navigate", 0.45);
      if (btn.dataset.view === "clone" || btn.dataset.view === "voices") loadVoices();
    });
  });

  // ── Language selects ──────────────────────────────────
  for (const id of ["gen-language", "clone-language", "upload-language"]) {
    const sel = $("#" + id);
    sel.innerHTML = LANGUAGES.map((l) => `<option value="${l}">${l}</option>`).join("");
    sel.value = "English";
  }

  // ── Char counters ─────────────────────────────────────
  function bindCounter(taId, countId) {
    const ta = $("#" + taId), count = $("#" + countId);
    ta.addEventListener("input", () => {
      count.textContent = `${ta.value.length} / 2000`;
      count.classList.toggle("hot", ta.value.length > 1800);
    });
  }
  bindCounter("gen-text", "gen-count");
  bindCounter("clone-text", "clone-count");

  // ── Generate view ─────────────────────────────────────
  let genMode = "speaker";

  $$(".mode-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      genMode = tab.dataset.mode;
      $$(".mode-tab").forEach((t) => {
        t.classList.toggle("active", t === tab);
        t.setAttribute("aria-selected", t === tab);
      });
      $("#speaker-fields").classList.toggle("hidden", genMode !== "speaker");
      $("#design-fields").classList.toggle("hidden", genMode !== "design");
      $("#library-fields").classList.toggle("hidden", genMode !== "library");
      if (genMode === "library") loadVoices();
      window.NarraRaven?.react("mode", 0.35);
    });
  });

  function renderGenPicker() {
    const picker = $("#gen-picker");
    if (!voices.length) {
      picker.innerHTML = `<p class="empty-line">No voices yet. Add one in the Voices tab.</p>`;
      $("#gen-picked-count").textContent = "0 selected";
      return;
    }
    picker.innerHTML = "";
    for (const v of voices) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "voice-pick" + (genPickedIds.has(v.voice_id) ? " picked" : "");
      b.textContent = v.name;
      b.addEventListener("click", () => {
        if (genPickedIds.has(v.voice_id)) genPickedIds.delete(v.voice_id);
        else if (genPickedIds.size < 5) genPickedIds.add(v.voice_id);
        else { toast("Five voices max", true); return; }
        renderGenPicker();
      });
      picker.appendChild(b);
    }
    $("#gen-picked-count").textContent = `${genPickedIds.size} selected · blend up to 5`;
  }

  const exRow = $("#design-examples");
  exRow.innerHTML = DESIGN_EXAMPLES.map((e) => `<button type="button" class="chip">${e}</button>`).join("");
  $$(".chip", exRow).forEach((chip) => {
    chip.addEventListener("click", () => {
      $("#gen-instruct").value = chip.textContent;
      $("#gen-instruct").focus();
    });
  });

  async function loadSpeakers() {
    const sel = $("#gen-speaker");
    try {
      const s = await api("/v1/speakers");
      const pretty = (sp) => sp.split("_").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");
      sel.innerHTML = s.speakers.map((sp) => `<option value="${sp}">${pretty(sp)}</option>`).join("");
    } catch (e) {
      sel.innerHTML = `<option value="">unavailable</option>`;
    }
  }

  // ── WAV encoding (mic recordings → 16-bit PCM mono) ───
  function encodeWav(audioBuffer) {
    const ch = audioBuffer.getChannelData(0);
    const rate = audioBuffer.sampleRate;
    const buf = new ArrayBuffer(44 + ch.length * 2);
    const dv = new DataView(buf);
    const wstr = (o, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(o + i, s.charCodeAt(i)); };
    wstr(0, "RIFF"); dv.setUint32(4, 36 + ch.length * 2, true); wstr(8, "WAVE");
    wstr(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true);
    dv.setUint16(22, 1, true); dv.setUint32(24, rate, true);
    dv.setUint32(28, rate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true);
    wstr(36, "data"); dv.setUint32(40, ch.length * 2, true);
    let o = 44;
    for (let i = 0; i < ch.length; i++, o += 2) {
      const s = Math.max(-1, Math.min(1, ch[i]));
      dv.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([buf], { type: "audio/wav" });
  }

  // ── Result rendering ──────────────────────────────────
  function pendingRow(container) {
    const div = document.createElement("div");
    div.className = "result-pending";
    div.innerHTML = `<span class="pending-bars"><span></span><span></span><span></span><span></span><span></span></span>
      <span>${LOADING_LINES[Math.floor(Math.random() * LOADING_LINES.length)]}</span>`;
    container.prepend(div);
    return div;
  }

  function drawWaveform(canvas, audioBuffer, progress = 0) {
    const dpr = Math.min(devicePixelRatio || 1, 2);
    const w = canvas.clientWidth || 300, h = canvas.clientHeight || 44;
    canvas.width = w * dpr; canvas.height = h * dpr;
    const c = canvas.getContext("2d");
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    c.clearRect(0, 0, w, h);
    const data = audioBuffer.getChannelData(0);
    const bars = Math.floor(w / 3);
    const step = Math.floor(data.length / bars) || 1;
    const played = Math.floor(bars * progress);
    for (let i = 0; i < bars; i++) {
      let peak = 0;
      const start = i * step;
      for (let j = 0; j < step; j += 16) peak = Math.max(peak, Math.abs(data[start + j] || 0));
      const bh = Math.max(2, peak * h * 0.92);
      c.fillStyle = i <= played && progress > 0
        ? "oklch(0.78 0.145 72)"
        : "oklch(0.44 0.015 78 / 0.8)";
      c.fillRect(i * 3, (h - bh) / 2, 2, bh);
    }
  }

  async function saveBlobAsVoice(blob, { name, transcript, language, tags }, btn) {
    btn.disabled = true;
    const fd = new FormData();
    fd.append("file", new File([blob], "generated.wav", { type: "audio/wav" }));
    fd.append("name", name);
    fd.append("language", language || "English");
    if (transcript) fd.append("transcript", transcript);
    if (tags) fd.append("tags", tags);
    try {
      await api("/v1/voices", { method: "POST", body: fd });
      toast("Saved to voice library");
      btn.textContent = "saved";
      loadVoices();
    } catch (e) {
      toast(e.message, true);
      btn.disabled = false;
    }
  }

  function resultRow(container, { base64, meta, label, save }) {
    const bytes = Uint8Array.from(atob(base64), (ch) => ch.charCodeAt(0));
    const blob = new Blob([bytes], { type: "audio/wav" });
    const url = URL.createObjectURL(blob);
    const el = new Audio(url);
    el.crossOrigin = "anonymous";

    const row = document.createElement("div");
    row.className = "result-row";
    row.innerHTML = `
      <button class="result-play" type="button" aria-label="Play">▶</button>
      <canvas class="result-wave" aria-hidden="true"></canvas>
      <div class="result-meta">
        <span class="rm-text"></span>
        ${meta.duration_s.toFixed(1)}s · ${meta.model}
      </div>
      <a class="result-dl" download="tts-${Date.now()}.wav">wav</a>`;
    row.querySelector(".rm-text").textContent = label;
    row.querySelector(".result-dl").href = url;

    if (save) {
      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.className = "result-dl";
      saveBtn.textContent = "save voice";
      saveBtn.title = "Save this audio as a reference voice for cloning";
      saveBtn.addEventListener("click", () => saveBlobAsVoice(blob, save, saveBtn));
      row.appendChild(saveBtn);
    }

    const btn = row.querySelector(".result-play");
    const canvas = row.querySelector(".result-wave");
    btn.addEventListener("click", () => togglePlay(el, btn));

    container.prepend(row);

    // Decode for waveform + progress updates.
    ensureCtx().decodeAudioData(bytes.buffer.slice(0)).then((buf) => {
      drawWaveform(canvas, buf);
      el.addEventListener("timeupdate", () => drawWaveform(canvas, buf, el.currentTime / el.duration || 0));
      el.addEventListener("ended", () => drawWaveform(canvas, buf, 0));
      canvas.addEventListener("click", (e) => {
        const r = canvas.getBoundingClientRect();
        el.currentTime = ((e.clientX - r.left) / r.width) * el.duration;
        if (el.paused) togglePlay(el, btn);
      });
    });

    // Autoplay the fresh result — the moment of delight.
    togglePlay(el, btn);
  }

  async function runGeneration(container, submitBtn, endpoint, payload, label, save) {
    const pending = pendingRow(container);
    submitBtn.disabled = true;
    window.Swarm.kick(0.5);
    window.NarraRaven?.setState("thinking");
    try {
      const res = await api(endpoint, { method: "POST", json: payload });
      resultRow(container, { base64: res.audio_base64, meta: res, label, save });
      window.NarraRaven?.react("success", 1);
    } catch (e) {
      const err = document.createElement("div");
      err.className = "result-err";
      err.textContent = e.message;
      container.prepend(err);
      setTimeout(() => err.remove(), 8000);
    } finally {
      pending.remove();
      submitBtn.disabled = false;
      if (!current) window.NarraRaven?.setState("idle");
    }
  }

  $("#gen-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("#gen-text").value.trim();
    if (!text) return;
    const language = $("#gen-language").value;
    const container = $("#gen-results");
    const btn = $("#gen-submit");

    if (genMode === "speaker") {
      const speaker = $("#gen-speaker").value;
      if (!speaker) { toast("No speaker available yet", true); return; }
      const instruct = $("#gen-instruct-opt").value.trim() || null;
      runGeneration(container, btn, "/v1/tts/custom-voice",
        { text, speaker, language, instruct }, `${speaker} · "${text}"`,
        { name: `${speaker}${instruct ? " — " + instruct.slice(0, 30) : ""}`, transcript: text, language, tags: "built-in" });
    } else if (genMode === "library") {
      if (!genPickedIds.size) { toast("Pick one of your voices first", true); return; }
      const names = voices.filter((v) => genPickedIds.has(v.voice_id)).map((v) => v.name).join(" + ");
      runGeneration(container, btn, "/v1/tts/voice-clone", {
        text,
        voice_ids: [...genPickedIds],
        language,
        x_vector_only: true,
        model: $("#gen-clone-model").value,
      }, `${names} · "${text}"`,
        { name: `${names.slice(0, 40)} — generated`, transcript: text, language, tags: "generated" });
    } else {
      const instruct = $("#gen-instruct").value.trim();
      if (instruct.length < 5) { toast("Describe the voice first (5+ characters)", true); return; }
      runGeneration(container, btn, "/v1/tts/voice-design",
        { text, instruct, language }, `${instruct} · "${text}"`,
        { name: instruct.slice(0, 48), transcript: text, language, tags: "voice-design" });
    }
  });

  // ── Clone view ────────────────────────────────────────
  function renderPicker() {
    const picker = $("#clone-picker");
    if (!voices.length) {
      picker.innerHTML = `<p class="empty-line">No voices in the library yet. Add one in the Voices tab.</p>`;
      return;
    }
    picker.innerHTML = "";
    for (const v of voices) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "voice-pick" + (pickedVoiceIds.has(v.voice_id) ? " picked" : "");
      b.textContent = v.name;
      b.addEventListener("click", () => {
        if (pickedVoiceIds.has(v.voice_id)) pickedVoiceIds.delete(v.voice_id);
        else if (pickedVoiceIds.size < 5) pickedVoiceIds.add(v.voice_id);
        else { toast("Five references max", true); return; }
        renderPicker();
      });
      picker.appendChild(b);
    }
    $("#clone-picked-count").textContent = `${pickedVoiceIds.size} selected`;
  }

  $("#clone-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = $("#clone-text").value.trim();
    if (!text) return;
    if (!pickedVoiceIds.size) { toast("Pick at least one reference voice", true); return; }
    const payload = {
      text,
      voice_ids: [...pickedVoiceIds],
      language: $("#clone-language").value,
      x_vector_only: $("#clone-xvec").checked,
      model: $("#clone-model").value,
    };
    const names = voices.filter((v) => pickedVoiceIds.has(v.voice_id)).map((v) => v.name).join(" + ");
    runGeneration($("#clone-results"), $("#clone-form .btn-primary"),
      "/v1/tts/voice-clone", payload, `${names} · "${text}"`,
      { name: `${names.slice(0, 40)} — clone`, transcript: text, language: payload.language, tags: "cloned" });
  });

  // ── Voices view ───────────────────────────────────────
  function fmtDuration(s) {
    return s >= 60 ? `${Math.floor(s / 60)}m ${Math.round(s % 60)}s` : `${s.toFixed(1)}s`;
  }

  async function loadVoices() {
    try {
      const res = await api("/v1/voices");
      voices = res.voices.sort((a, b) => b.created_at - a.created_at);
    } catch (e) {
      voices = [];
    }
    renderPicker();
    renderGenPicker();
    renderVoiceList();
  }

  function renderVoiceList() {
    const list = $("#voice-list");
    if (!voices.length) {
      list.innerHTML = `<p class="empty-line">The library is silent. Drop a reference sample above to begin.</p>`;
      return;
    }
    list.innerHTML = "";
    for (const v of voices) {
      const row = document.createElement("div");
      row.className = "voice-row";
      row.innerHTML = `
        <button class="vr-play" type="button" aria-label="Play sample">▶</button>
        <div class="vr-info">
          <div class="vr-name"></div>
          <div class="vr-sub">${fmtDuration(v.duration_s)} · ${(v.size_bytes / 1024 / 1024).toFixed(1)} MB · ${v.language}${v.has_transcript ? " · transcript" : ""}</div>
        </div>
        <div class="vr-actions">
          <button class="vr-btn" data-act="edit" type="button">edit</button>
          <button class="vr-btn" data-act="isolate" type="button" title="Strip background music (demucs)">isolate vocals</button>
          <button class="vr-btn danger" data-act="delete" type="button">delete</button>
        </div>`;
      const nameEl = row.querySelector(".vr-name");
      nameEl.textContent = v.name;
      for (const t of v.tags) {
        const tag = document.createElement("span");
        tag.className = "vr-tag";
        tag.textContent = t;
        nameEl.appendChild(tag);
      }

      const playBtn = row.querySelector(".vr-play");
      playBtn.addEventListener("click", async () => {
        if (row._audio && current && current.el === row._audio && !row._audio.paused) { stopCurrent(); return; }
        try {
          if (!row._audio) {
            playBtn.disabled = true;
            const res = await fetch(`/v1/voices/${v.voice_id}/audio`, { headers: { Authorization: `Bearer ${apiKey}` } });
            if (!res.ok) throw new Error("Could not fetch audio");
            row._audio = new Audio(URL.createObjectURL(await res.blob()));
            playBtn.disabled = false;
          }
          togglePlay(row._audio, playBtn);
        } catch (err) {
          playBtn.disabled = false;
          toast(err.message, true);
        }
      });

      row.querySelector('[data-act="edit"]').addEventListener("click", () => {
        const existing = row.nextElementSibling;
        if (existing && existing.classList.contains("vr-editor")) { existing.remove(); return; }
        $$(".vr-editor", list).forEach((e) => e.remove());
        const ed = document.createElement("div");
        ed.className = "vr-editor";
        ed.innerHTML = `
          <div class="field-row">
            <label class="field grow">
              <span class="field-label">Name</span>
              <input type="text" data-f="name">
            </label>
            <label class="field">
              <span class="field-label">Language</span>
              <select data-f="language">${LANGUAGES.map((l) => `<option>${l}</option>`).join("")}</select>
            </label>
          </div>
          <label class="field">
            <span class="field-label">Transcript <i>improves cloning accuracy</i></span>
            <input type="text" data-f="transcript" placeholder="Exact words spoken in the sample">
          </label>
          <div class="chip-row">
            <button class="chip" data-f="whisper" type="button">↻ auto-transcribe with Whisper</button>
          </div>
          <label class="field">
            <span class="field-label">Tags <i>comma-separated</i></span>
            <input type="text" data-f="tags" placeholder="e.g. warm, narration">
          </label>
          <div class="field-row">
            <div class="grow"></div>
            <button class="btn-ghost" data-f="cancel" type="button">Cancel</button>
            <button class="btn-primary" data-f="save" type="button">Save</button>
          </div>`;
        ed.querySelector('[data-f="name"]').value = v.name;
        ed.querySelector('[data-f="language"]').value = v.language;
        ed.querySelector('[data-f="tags"]').value = v.tags.join(", ");
        ed.querySelector('[data-f="cancel"]').addEventListener("click", () => ed.remove());
        ed.querySelector('[data-f="whisper"]').addEventListener("click", async (e) => {
          const wBtn = e.currentTarget;
          wBtn.disabled = true;
          wBtn.textContent = "transcribing…";
          try {
            const res = await api(`/v1/voices/${v.voice_id}/transcribe`, { method: "POST" });
            ed.querySelector('[data-f="transcript"]').value = res.transcript;
            toast("Transcribed");
          } catch (err) {
            toast(err.message, true);
          } finally {
            wBtn.disabled = false;
            wBtn.textContent = "↻ auto-transcribe with Whisper";
          }
        });
        ed.querySelector('[data-f="save"]').addEventListener("click", async () => {
          const btn = ed.querySelector('[data-f="save"]');
          btn.disabled = true;
          const body = {
            name: ed.querySelector('[data-f="name"]').value.trim() || v.name,
            language: ed.querySelector('[data-f="language"]').value,
            tags: ed.querySelector('[data-f="tags"]').value.split(",").map((t) => t.trim()).filter(Boolean),
          };
          const tr = ed.querySelector('[data-f="transcript"]').value.trim();
          if (tr) body.transcript = tr;
          try {
            await api(`/v1/voices/${v.voice_id}`, { method: "PATCH", json: body });
            toast("Voice updated");
            loadVoices();
          } catch (err) {
            toast(err.message, true);
            btn.disabled = false;
          }
        });
        row.after(ed);
        ed.querySelector('[data-f="name"]').focus();
      });

      row.querySelector('[data-act="isolate"]').addEventListener("click", async (e) => {
        const btn = e.currentTarget;
        btn.disabled = true;
        btn.textContent = "isolating…";
        try {
          await api("/v1/audio/isolate-vocals", { method: "POST", json: { voice_id: v.voice_id } });
          toast("Vocals isolated — new voice added");
          loadVoices();
        } catch (err) {
          toast(err.message, true);
          btn.disabled = false;
          btn.textContent = "isolate vocals";
        }
      });

      row.querySelector('[data-act="delete"]').addEventListener("click", async () => {
        if (!confirm(`Delete "${v.name}"? This cannot be undone.`)) return;
        try {
          await api(`/v1/voices/${v.voice_id}`, { method: "DELETE" });
          pickedVoiceIds.delete(v.voice_id);
          genPickedIds.delete(v.voice_id);
          toast("Deleted");
          loadVoices();
        } catch (err) { toast(err.message, true); }
      });

      list.appendChild(row);
    }
  }

  // ── Microphone recording ──────────────────────────────
  let recStream = null, recorder = null, recChunks = [], recTimer = null, recStart = 0;

  function recUI(state) { // idle | live
    $("#rec-btn").classList.toggle("hidden", state !== "idle");
    $("#rec-live").classList.toggle("hidden", state !== "live");
    $("#rec-stop").classList.toggle("hidden", state !== "live");
    $("#rec-cancel").classList.toggle("hidden", state !== "live");
  }

  function recCleanup() {
    clearInterval(recTimer);
    if (recStream) recStream.getTracks().forEach((t) => t.stop());
    recStream = null; recorder = null; recChunks = [];
    recUI("idle");
  }

  $("#rec-btn").addEventListener("click", async () => {
    try {
      recStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
    } catch (e) {
      toast("Microphone access denied or unavailable", true);
      return;
    }
    recChunks = [];
    recorder = new MediaRecorder(recStream);
    recorder.addEventListener("dataavailable", (e) => { if (e.data.size) recChunks.push(e.data); });
    recorder.start();
    recStart = performance.now();
    recUI("live");
    window.Swarm.kick(0.5);
    window.NarraRaven?.setState("recording");
    recTimer = setInterval(() => {
      const s = Math.floor((performance.now() - recStart) / 1000);
      $("#rec-time").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    }, 250);
  });

  $("#rec-cancel").addEventListener("click", () => {
    if (recorder && recorder.state !== "inactive") recorder.stop();
    recCleanup();
    window.NarraRaven?.setState("idle");
  });

  $("#rec-stop").addEventListener("click", () => {
    if (!recorder) return;
    recorder.addEventListener("stop", async () => {
      try {
        const raw = new Blob(recChunks, { type: recorder.mimeType });
        const pcm = await ensureCtx().decodeAudioData(await raw.arrayBuffer());
        if (pcm.duration < 1) { toast("Recording too short — aim for 5-15 seconds", true); recCleanup(); return; }
        const wav = encodeWav(pcm);
        recCleanup();
        const stamp = new Date().toTimeString().slice(0, 5);
        beginUpload(new File([wav], `mic-recording-${stamp}.wav`, { type: "audio/wav" }));
        window.NarraRaven?.setState("idle");
      } catch (e) {
        toast(`Could not process recording: ${e.message}`, true);
        recCleanup();
        window.NarraRaven?.setState("idle");
      }
    }, { once: true });
    recorder.stop();
  });

  // Upload flow
  const dropzone = $("#dropzone");
  const fileInput = $("#file-input");

  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") fileInput.click(); });
  ["dragover", "dragenter"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.add("drag"); }));
  ["dragleave", "drop"].forEach((ev) => dropzone.addEventListener(ev, (e) => { e.preventDefault(); dropzone.classList.remove("drag"); }));
  dropzone.addEventListener("drop", (e) => {
    const f = e.dataTransfer.files[0];
    if (f) beginUpload(f);
  });
  fileInput.addEventListener("change", () => { if (fileInput.files[0]) beginUpload(fileInput.files[0]); });

  function beginUpload(file) {
    pendingFile = file;
    $("#upload-filename").textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(1)} MB`;
    $("#upload-name").value = file.name.replace(/\.[^.]+$/, "").replace(/[-_]/g, " ");
    $("#upload-meta").classList.remove("hidden");
    $("#upload-name").focus();
  }

  async function autoTranscribe(voiceId) {
    try {
      const res = await api(`/v1/voices/${voiceId}/transcribe`, { method: "POST" });
      toast(`Transcribed: "${res.transcript.slice(0, 60)}${res.transcript.length > 60 ? "…" : ""}"`);
      loadVoices();
    } catch (e) {
      toast(`Auto-transcription failed: ${e.message}`, true);
    }
  }

  $("#upload-cancel").addEventListener("click", () => {
    pendingFile = null;
    fileInput.value = "";
    $("#upload-meta").classList.add("hidden");
  });

  $("#upload-confirm").addEventListener("click", async () => {
    if (!pendingFile) return;
    const btn = $("#upload-confirm");
    btn.disabled = true;
    const fd = new FormData();
    fd.append("file", pendingFile);
    fd.append("name", $("#upload-name").value.trim() || pendingFile.name);
    fd.append("language", $("#upload-language").value);
    try {
      const created = await api("/v1/voices", { method: "POST", body: fd });
      toast("Voice added — transcribing in the background");
      window.Swarm.kick(0.6);
      $("#upload-cancel").click();
      loadVoices();
      autoTranscribe(created.voice_id);
    } catch (e) {
      toast(e.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  // ── Docs view ─────────────────────────────────────────
  const CURL_AUTH = `-H "Authorization: Bearer $TTS_API_KEY"`;
  const DOCS = [
    { group: "Text to speech", eps: [
      { m: "POST", p: "/v1/tts/custom-voice", s: "Speak with a built-in speaker",
        d: "Synthesize text with a preset speaker. Optional instruct steers style and emotion.",
        curl: `curl -s localhost:8765/v1/tts/custom-voice ${CURL_AUTH} \\\n  -H "Content-Type: application/json" \\\n  -d '{"text": "Hello from my Mac.", "speaker": "Ethan", "language": "English", "instruct": "sound excited", "output_format": "url"}'` },
      { m: "POST", p: "/v1/tts/voice-design", s: "Voice from a text description",
        d: "Describe a voice in plain language; the model designs and speaks with it. instruct is 5 to 500 characters.",
        curl: `curl -s localhost:8765/v1/tts/voice-design ${CURL_AUTH} \\\n  -H "Content-Type: application/json" \\\n  -d '{"text": "The tide waits for no one.", "instruct": "A weathered sea captain, slow and salty", "output_format": "url"}'` },
      { m: "POST", p: "/v1/tts/voice-clone", s: "Clone from reference voices",
        d: "Clone from 1 to 5 stored voices (embeddings averaged). x_vector_only true skips transcripts. Models: base-1.7b (quality) or base-0.6b (fast).",
        curl: `curl -s localhost:8765/v1/tts/voice-clone ${CURL_AUTH} \\\n  -H "Content-Type: application/json" \\\n  -d '{"text": "Now I sound like you.", "voice_ids": ["<voice_id>"], "x_vector_only": true, "model": "base-1.7b", "output_format": "url"}'` },
    ]},
    { group: "Voice library", eps: [
      { m: "GET", p: "/v1/voices", s: "List stored voices",
        d: "Every uploaded reference voice with id, name, duration, language, tags.",
        curl: `curl -s localhost:8765/v1/voices ${CURL_AUTH}` },
      { m: "POST", p: "/v1/voices", s: "Upload a reference voice",
        d: "Multipart upload: file (wav/mp3/flac/ogg/m4a), name, language, transcript, tags (comma-separated). Returns the new voice_id.",
        curl: `curl -s localhost:8765/v1/voices ${CURL_AUTH} \\\n  -F "file=@sample.wav" -F "name=Lance warm read" -F "language=English"` },
      { m: "GET", p: "/v1/voices/{id}", s: "Voice metadata",
        d: "Fetch one voice's metadata by id.",
        curl: `curl -s localhost:8765/v1/voices/<voice_id> ${CURL_AUTH}` },
      { m: "POST", p: "/v1/voices/{id}/transcribe", s: "Auto-transcribe with Whisper",
        d: "Runs faster-whisper on the stored audio and saves the result as the voice's transcript. Returns the transcript.",
        curl: `curl -s -X POST localhost:8765/v1/voices/<voice_id>/transcribe ${CURL_AUTH}` },
      { m: "PATCH", p: "/v1/voices/{id}", s: "Update name, transcript, tags",
        d: "Partial update. Send only the fields you want to change.",
        curl: `curl -s -X PATCH localhost:8765/v1/voices/<voice_id> ${CURL_AUTH} \\\n  -H "Content-Type: application/json" -d '{"name": "New name"}'` },
      { m: "DELETE", p: "/v1/voices/{id}", s: "Delete a voice",
        d: "Removes the voice and its audio file. 204 on success.",
        curl: `curl -s -X DELETE localhost:8765/v1/voices/<voice_id> ${CURL_AUTH}` },
      { m: "GET", p: "/v1/voices/{id}/audio", s: "Download original audio",
        d: "Streams the stored reference file.",
        curl: `curl -s localhost:8765/v1/voices/<voice_id>/audio ${CURL_AUTH} -o voice.wav` },
    ]},
    { group: "Audio tools", eps: [
      { m: "POST", p: "/v1/audio/isolate-vocals", s: "Strip background music",
        d: "Runs demucs on a stored voice and saves the isolated vocals as a new voice (tagged vocals-only).",
        curl: `curl -s localhost:8765/v1/audio/isolate-vocals ${CURL_AUTH} \\\n  -H "Content-Type: application/json" -d '{"voice_id": "<voice_id>"}'` },
      { m: "GET", p: "/v1/outputs/{id}.wav", s: "Download a generated output",
        d: "Fetch a result generated with output_format \"url\". Outputs expire after TTS_OUTPUT_TTL seconds (default 3600).",
        curl: `curl -s localhost:8765/v1/outputs/<output_id>.wav ${CURL_AUTH} -o out.wav` },
    ]},
    { group: "Service", eps: [
      { m: "GET", p: "/health", s: "Status, device, loaded model",
        d: "Reports ok or loading, the warm model, and the inference device (mps, cuda, cpu).",
        curl: `curl -s localhost:8765/health ${CURL_AUTH}` },
      { m: "GET", p: "/v1/models", s: "Models and capabilities",
        d: "All model keys grouped by capability (clone, design, custom).",
        curl: `curl -s localhost:8765/v1/models ${CURL_AUTH}` },
      { m: "GET", p: "/v1/languages", s: "Supported languages",
        d: "Languages for a given model (query param model, optional).",
        curl: `curl -s localhost:8765/v1/languages ${CURL_AUTH}` },
      { m: "GET", p: "/v1/speakers", s: "Built-in speakers",
        d: "Preset speaker names for the CustomVoice models.",
        curl: `curl -s localhost:8765/v1/speakers ${CURL_AUTH}` },
    ]},
  ];

  function renderDocs() {
    const root = $("#docs-list");
    for (const group of DOCS) {
      const title = document.createElement("p");
      title.className = "docs-group-title";
      title.textContent = group.group;
      root.appendChild(title);
      for (const ep of group.eps) {
        const div = document.createElement("div");
        div.className = "ep";
        div.innerHTML = `
          <button class="ep-head" type="button" aria-expanded="false">
            <span class="ep-method ${ep.m.toLowerCase()}">${ep.m}</span>
            <span class="ep-path">${ep.p}</span>
            <span class="ep-summary">${ep.s}</span>
          </button>
          <div class="ep-body">
            <p>${ep.d}</p>
            <pre><button class="copy-btn" type="button">copy</button><code></code></pre>
          </div>`;
        div.querySelector("code").textContent = ep.curl;
        div.querySelector(".ep-head").addEventListener("click", () => {
          const open = div.classList.toggle("open");
          div.querySelector(".ep-head").setAttribute("aria-expanded", open);
        });
        div.querySelector(".copy-btn").addEventListener("click", (e) => {
          navigator.clipboard.writeText(ep.curl);
          e.currentTarget.textContent = "copied";
          setTimeout(() => { e.currentTarget && (e.currentTarget.textContent = "copy"); }, 1500);
          toast("curl copied");
        });
        root.appendChild(div);
      }
    }
  }

  // ── API key dialog ────────────────────────────────────
  $("#key-btn").addEventListener("click", () => {
    $("#key-input").value = apiKey;
    $("#key-scrim").classList.remove("hidden");
    $("#key-input").focus();
  });
  $("#key-cancel").addEventListener("click", () => $("#key-scrim").classList.add("hidden"));
  $("#key-scrim").addEventListener("click", (e) => { if (e.target === e.currentTarget) $("#key-scrim").classList.add("hidden"); });
  $("#key-save").addEventListener("click", () => {
    apiKey = $("#key-input").value.trim();
    if (apiKey) localStorage.setItem(KEY_STORAGE, apiKey);
    else localStorage.removeItem(KEY_STORAGE);
    $("#key-scrim").classList.add("hidden");
    toast("Key saved");
    pollHealth();
    loadSpeakers();
    loadVoices();
  });
  $("#key-input").addEventListener("keydown", (e) => { if (e.key === "Enter") $("#key-save").click(); });

  // ── Boot ──────────────────────────────────────────────
  renderDocs();
  pollHealth();
  setInterval(pollHealth, 12000);
  loadSpeakers();
  loadVoices();
})();
