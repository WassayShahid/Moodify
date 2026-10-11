const FACE_API = "https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.15";
const PICKS = 5;
const SCAN_MS = 900;
const STABLE_MS = 2500; // a new mood must hold this long before picks change

const EMOJI = { happy: "😊", energetic: "⚡", calm: "🌊", neutral: "😐", sad: "🌧️", angry: "🔥" };
const COLOR = { happy: "--mood-happy", energetic: "--mood-energetic", calm: "--mood-calm",
                neutral: "--mood-neutral", sad: "--mood-sad", angry: "--mood-angry" };
// face-api expressions -> music moods. Fear gets calming music; surprise gets energy.
const FACE_TO_MOOD = { happy: "happy", surprised: "energetic", neutral: "neutral", sad: "sad",
                       angry: "angry", disgusted: "angry", fearful: "calm" };
const NEIGHBOURS = { happy: ["energetic", "calm", "neutral"], energetic: ["happy", "angry", "neutral"],
                     calm: ["neutral", "sad", "happy"], neutral: ["calm", "happy", "energetic"],
                     sad: ["calm", "neutral"], angry: ["energetic", "sad", "neutral"] };
const LABELS = window.MOOD_LABELS;

const $ = (id) => document.getElementById(id);
const state = { playlist: null, mood: null, picks: [], source: null };

// ---------- helpers ----------
let toastTimer;
function toast(html, { error = false, ms = 4500 } = {}) {
  const el = $("toast");
  el.innerHTML = html;
  el.classList.toggle("error", error);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), ms);
}

function busy(btn, on, label) {
  btn.disabled = on;
  if (on) { btn.dataset.label = btn.innerHTML; btn.innerHTML = `<span class="spinner"></span> ${label}`; }
  else if (btn.dataset.label) btn.innerHTML = btn.dataset.label;
}

function shuffle(arr) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- playlist ----------
async function loadPlaylist(body, btn) {
  busy(btn, true, "Sorting songs…");
  try {
    const res = await fetch("/api/playlist", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Couldn't load that playlist.");
    setPlaylist(data);
    toast(`Sorted <b>${data.tracks.length}</b> songs by mood ✨`);
  } catch (e) {
    toast(escapeHtml(e.message), { error: true, ms: 8000 });
  } finally {
    busy(btn, false);
  }
}

function setPlaylist(data) {
  state.playlist = data;
  try { sessionStorage.setItem("moodify.playlist", JSON.stringify(data)); } catch {}
  $("playlist-head").classList.remove("hidden");
  $("pl-name").textContent = data.name;
  $("pl-meta").textContent = `${data.tracks.length} songs${data.owner ? " · " + data.owner : ""}`;
  $("pl-img").classList.toggle("hidden", !data.image);
  $("pl-ph").classList.toggle("hidden", !!data.image);
  if (data.image) $("pl-img").src = data.image;
  renderChart();
  if (state.mood) pickSongs();
}

function renderChart() {
  const counts = state.playlist?.counts || {};
  const max = Math.max(1, ...Object.values(counts));
  document.querySelectorAll(".bar-row").forEach((row) => {
    const m = row.dataset.mood, n = counts[m] || 0;
    row.querySelector(".fill").style.width = `${(n / max) * 100}%`;
    row.querySelector(".n").textContent = n;
    row.classList.toggle("active", m === state.mood);
    row.title = `${LABELS[m]}: ${n} song${n === 1 ? "" : "s"}`;
  });
}

// ---------- recommendations ----------
function pickSongs() {
  const tracks = state.playlist?.tracks || [];
  if (!tracks.length || !state.mood) return renderRecs();
  let pool = tracks.filter((t) => t.mood === state.mood);
  let borrowed = false;
  for (const near of NEIGHBOURS[state.mood]) {
    if (pool.length >= PICKS) break;
    const extra = tracks.filter((t) => t.mood === near);
    if (extra.length) { borrowed = true; pool = pool.concat(shuffle(extra).slice(0, PICKS - pool.length)); }
  }
  state.picks = shuffle(pool).slice(0, PICKS);
  state.borrowed = borrowed;
  renderRecs();
}

function renderRecs() {
  const recs = $("recs");
  $("shuffle-btn").disabled = $("save-btn").disabled = !state.picks.length;
  if (!state.playlist) { recs.innerHTML = `<div class="empty">Load a playlist to get picks.</div>`; return; }
  if (!state.mood) { recs.innerHTML = `<div class="empty">Start the camera or click a mood to get picks.</div>`; return; }
  $("recs-title").textContent = `${EMOJI[state.mood]} ${LABELS[state.mood]} picks`;
  if (!state.picks.length) { recs.innerHTML = `<div class="empty">No songs in this playlist fit that mood.</div>`; return; }
  recs.innerHTML = (state.borrowed ? `<p class="hint" style="margin:0 0 4px">Not many ${state.mood} songs here, so we added some nearby moods.</p>` : "") +
    state.picks.map((t) =>
      `<iframe loading="lazy" title="${escapeHtml(t.name)} by ${escapeHtml(t.artist)}"
        src="https://open.spotify.com/embed/track/${encodeURIComponent(t.id)}?utm_source=moodify&theme=0"
        allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"></iframe>`).join("");
}

function setMood(mood, { source, confidence } = {}) {
  const changed = mood !== state.mood;
  state.mood = mood;
  state.source = source;
  $("mood-emoji").textContent = EMOJI[mood];
  $("mood-label").textContent = LABELS[mood];
  $("mood-sub").textContent = source === "camera" ? "Detected from your expression" : "Picked by you";
  $("mood-conf").textContent = confidence ? `${Math.round(confidence * 100)}% sure` : "";
  const color = getComputedStyle(document.documentElement).getPropertyValue(COLOR[mood]);
  $("mood-now").style.borderColor = color;
  $("mood-now").style.boxShadow = `0 0 30px ${color}33`;
  renderChart();
  if (changed) pickSongs();
}

// ---------- camera + face-api ----------
let faceapi, stream, scanTimer, smoothed = null, candidate = null, candidateSince = 0;

async function loadFaceApi() {
  if (faceapi) return faceapi;
  faceapi = await import(`${FACE_API}/dist/face-api.esm.js`);
  await Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri(`${FACE_API}/model`),
    faceapi.nets.faceExpressionNet.loadFromUri(`${FACE_API}/model`),
  ]);
  return faceapi;
}

async function startCamera() {
  const btn = $("cam-btn");
  busy(btn, true, "Loading model…");
  try {
    const [api, s] = await Promise.all([
      loadFaceApi(),
      navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" }, audio: false }),
    ]);
    stream = s;
    $("video").srcObject = stream;
    $("cam").classList.add("on");
    $("cam-placeholder").classList.add("hidden");
    busy(btn, false);
    btn.textContent = "Stop camera";
    btn.classList.replace("btn-primary", "btn-ghost");
    const opts = new api.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.45 });
    scanTimer = setInterval(() => scan(api, opts), SCAN_MS);
  } catch (e) {
    busy(btn, false);
    const msg = e.name === "NotAllowedError" ? "Camera permission was blocked. Allow it in your browser's address bar."
      : e.name === "NotFoundError" ? "No camera found on this device."
      : "Couldn't start mood detection: " + e.message;
    toast(escapeHtml(msg), { error: true, ms: 7000 });
    stopCamera();
  }
}

function stopCamera() {
  clearInterval(scanTimer);
  stream?.getTracks().forEach((t) => t.stop());
  stream = null; smoothed = null; candidate = null;
  $("video").srcObject = null;
  $("cam").classList.remove("on");
  $("cam-placeholder").classList.remove("hidden");
  const btn = $("cam-btn");
  btn.textContent = "Start camera";
  btn.classList.replace("btn-ghost", "btn-primary");
}

let scanning = false;
async function scan(api, opts) {
  if (scanning || !stream) return;
  scanning = true;
  try {
    const result = await api.detectSingleFace($("video"), opts).withFaceExpressions();
    if (!result) {
      if (state.source !== "manual") $("mood-sub").textContent = "Looking for your face…";
      return;
    }
    // Fold face expressions into music moods, then smooth over time (EMA).
    const scores = {};
    for (const [expr, p] of Object.entries(result.expressions)) {
      const m = FACE_TO_MOOD[expr];
      if (m) scores[m] = (scores[m] || 0) + p;
    }
    smoothed = smoothed
      ? Object.fromEntries(Object.keys(scores).map((m) => [m, smoothed[m] * 0.6 + scores[m] * 0.4]))
      : scores;
    const [top, conf] = Object.entries(smoothed).sort((a, b) => b[1] - a[1])[0];

    const now = Date.now();
    if (top !== candidate) { candidate = top; candidateSince = now; }
    if (top === state.mood) {
      setMood(top, { source: "camera", confidence: conf });
    } else if (!state.mood || now - candidateSince >= STABLE_MS) {
      setMood(top, { source: "camera", confidence: conf });
    }
  } catch (e) {
    console.warn("Detection error", e);
  } finally {
    scanning = false;
  }
}

// ---------- save to Spotify ----------
async function savePicks(pending) {
  const body = pending || { mood: state.mood, track_ids: state.picks.map((t) => t.id) };
  const btn = $("save-btn");
  busy(btn, true, "Saving…");
  try {
    const res = await fetch("/api/save", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.status === 401) {
      try { sessionStorage.setItem("moodify.pendingSave", JSON.stringify(body)); } catch {}
      location.href = data.login_url;
      return;
    }
    if (!res.ok) throw new Error(data.error || "Couldn't save the playlist.");
    toast(`Saved <b>${escapeHtml(data.name)}</b>. <a href="${encodeURI(data.url)}" target="_blank" rel="noopener">Open in Spotify →</a>`, { ms: 9000 });
  } catch (e) {
    toast(escapeHtml(e.message), { error: true });
  } finally {
    busy(btn, false);
    btn.disabled = !state.picks.length;
  }
}

// ---------- wire up ----------
$("playlist-form").addEventListener("submit", (e) => {
  e.preventDefault();
  loadPlaylist({ url: $("playlist-url").value }, $("load-btn"));
});
$("demo-btn").addEventListener("click", () => loadPlaylist({ demo: true }, $("demo-btn")));
$("cam-btn").addEventListener("click", () => (stream ? stopCamera() : startCamera()));
$("shuffle-btn").addEventListener("click", pickSongs);
$("save-btn").addEventListener("click", () => savePicks());
document.querySelectorAll(".bar-row").forEach((row) =>
  row.addEventListener("click", () => {
    if (stream) stopCamera();
    const same = row.dataset.mood === state.mood;
    setMood(row.dataset.mood, { source: "manual" });
    if (same) pickSongs();
  }));

// Restore after the Spotify login redirect.
try {
  const saved = sessionStorage.getItem("moodify.playlist");
  if (saved) setPlaylist(JSON.parse(saved));
  const pending = sessionStorage.getItem("moodify.pendingSave");
  if (pending && new URLSearchParams(location.search).get("resume") === "save") {
    sessionStorage.removeItem("moodify.pendingSave");
    const body = JSON.parse(pending);
    setMood(body.mood, { source: "manual" });
    history.replaceState(null, "", location.pathname);
    savePicks(body);
  }
} catch {}
