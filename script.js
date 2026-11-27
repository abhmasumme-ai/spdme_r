const API_BASE = location.origin;
const WS_URL = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws";
const $ = id => document.getElementById(id);
const escapeHtml = v => String(v ?? "").replace(/[&<>"']/g, c => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
}[c]));

const S = {
  ws: null,
  detectedMelbetId: null,
  selectedEntityId: null,
  selectedFormat: null,
  selectedFixture: null,
  activeEntityId: null,
  lockedMelbetId: null,
  isLocked: false,
  isVerified: false,
  guardKilled: false,
  mulling: { delivery: false, batsman: false, wicket: false },
  workerLaunched: { delivery: false, batsman: false, wicket: false },
  currentOver: null,
  overDots: [],
  lastEventAt: 0,
  stake: 15,
};

function log(msg, err) {
  const t = $("terminal");
  if (!t) return;
  const li = document.createElement("li");
  li.className = err ? "err" : "";
  li.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  t.appendChild(li);
  t.scrollTop = t.scrollHeight;
  while (t.children.length > 300) t.removeChild(t.firstChild);
}

async function postJson(path, body) {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return await res.json();
  } catch (e) {
    log(`# API Error: ${e.message}`, true);
    return null;
  }
}

/* ---------- Stake ---------- */
async function loadStake() {
  try {
    const r = await fetch(`${API_BASE}/api/stake`);
    const d = await r.json();
    if (d && d.status === "success") {
      S.stake = d.stake;
      const inp = $("stakeInput");
      if (inp) inp.value = d.stake;
      updateStakeButtons(d.stake);
    }
  } catch {}
}

function updateStakeButtons(val) {
  document.querySelectorAll(".stake-preset").forEach(b => {
    b.classList.toggle("active", Number(b.dataset.stake) === Number(val));
  });
}

async function applyStake(val) {
  const s = Number(val);
  if (!Number.isFinite(s) || s < 1) {
    log("# ❌ Stake ১-এর কম বা অবৈধ", true);
    return;
  }
  const r = await postJson("/api/stake", { stake: s });
  if (r && r.status === "success") {
    S.stake = r.stake;
    log(`# ✅ Stake = ${r.stake}`);
    const inp = $("stakeInput");
    if (inp) inp.value = r.stake;
    updateStakeButtons(r.stake);
  } else {
    log(`# ❌ ${r?.message || "Stake apply failed"}`, true);
  }
}

/* ---------- Ball / over dots ---------- */
function setBall(kind, value) {
  const ball = $("ball");
  if (!ball) return;
  const known = ["four", "six", "wicket", "dot", "run", "noball", "wide", "overdone", "freehit", "idle", "msg", "raw"];
  ball.className = "ball " + (known.includes(kind) ? kind : "run");
  const label = ball.querySelector("span");
  if (label) label.textContent = String(value ?? "");
  else ball.textContent = String(value ?? "");
}

function classifyEventText(ev) {
  const e = String(ev || "").trim().toLowerCase();
  if (!e) return { kind: "idle", label: "-" };
  if (/^(w|wicket|out|bowled|lbw|caught|stumped|run ?out)/.test(e)) return { kind: "wicket", label: "W" };
  if (/^(nb|no ?ball)/.test(e)) return { kind: "noball", label: String(ev).toUpperCase() };
  if (/^(wd|wide)/.test(e)) return { kind: "wide", label: String(ev).toUpperCase() };
  if (/^6$|^six/.test(e)) return { kind: "six", label: "6" };
  if (/^4$|^four/.test(e)) return { kind: "four", label: "4" };
  if (/^0$|^dot/.test(e)) return { kind: "dot", label: "0" };
  if (/^\d+$/.test(e)) return { kind: "run", label: String(parseInt(e, 10)) };
  return { kind: "raw", label: String(ev).slice(0, 60) };
}

function renderOverDots() {
  const c = $("overDots");
  if (!c) return;
  let h = "";
  for (let i = 0; i < 6; i++) {
    const v = S.overDots[i];
    if (v === "d") h += '<div class="od d">0</div>';
    else if (v === "f") h += '<div class="od f">4</div>';
    else if (v === "s") h += '<div class="od s">6</div>';
    else if (v === "w") h += '<div class="od w">W</div>';
    else if (v === "x") h += '<div class="od x">!</div>';
    else if (v === "r") h += '<div class="od">•</div>';
    else h += '<div class="od e">·</div>';
  }
  c.innerHTML = h;
}

function updateOverDots(over, ball, kind) {
  if (over == null) return;
  if (S.currentOver !== over) {
    S.currentOver = over;
    S.overDots = [];
  }
  const idx = Math.max(0, Math.min(5, (ball || 1) - 1));
  S.overDots[idx] =
    kind === "wicket" ? "w" :
    kind === "six" ? "s" :
    kind === "four" ? "f" :
    kind === "dot" ? "d" :
    (kind === "noball" || kind === "wide") ? "x" : "r";
  renderOverDots();
}

function updateOddsBar(lag) {
  if (lag == null) return;
  const h = Math.min(90, Math.max(4, lag / 5));
  if ($("barOdds")) $("barOdds").style.height = `${h}px`;
  if ($("barOddsTxt")) $("barOddsTxt").textContent = `${lag}ms`;
}

function updateClickBar(ms) {
  if (ms == null) return;
  const h = Math.min(90, Math.max(4, ms / 5));
  if ($("barClick")) $("barClick").style.height = `${h}px`;
  if ($("barClickTxt")) $("barClickTxt").textContent = `${ms}ms`;
}

function setEntityStatus(state, msgs) {
  const el = $("entityStatus");
  if (!el) return;
  if (state === "connected") {
    el.textContent = `● Connected${msgs ? ` (${msgs})` : ""}`;
    el.style.color = "var(--green)";
  } else if (state === "connecting") {
    el.textContent = "◐ Connecting…";
    el.style.color = "var(--yellow)";
  } else {
    el.textContent = `○ ${state || "Disconnected"}`;
    el.style.color = "var(--yellow)";
  }
}

function setGuard(killed) {
  S.guardKilled = !!killed;
  const b = $("bKill");
  if (!b) return;
  b.style.background = killed ? "var(--red)" : "";
  b.style.borderColor = killed ? "var(--red)" : "";
  b.style.color = killed ? "#fff" : "";
  b.title = killed ? "Kill-switch ON — click to resume" : "Kill-switch: stop all bets";
  b.innerHTML = killed ? '<i class="fa-solid fa-play"></i>' : '<i class="fa-solid fa-ban"></i>';
}

function setLock(isOn) {
  S.isLocked = isOn;
  const b = $("lockBtn");
  if (!b) return;
  if (isOn) {
    b.className = "lock-btn locked";
    b.innerHTML = '<i class="fa-solid fa-lock"></i> UNLOCK';
  } else {
    b.className = "lock-btn unlocked";
    b.innerHTML = '<i class="fa-solid fa-lock-open"></i> LOCK';
    setVerified(false);
  }
}

function setVerified(isOn) {
  S.isVerified = isOn;
  const b = $("verifyBtn");
  if (!b) return;
  b.classList.toggle("verified", isOn);
  b.textContent = isOn ? "VERIFIED ✓" : "VERIFY";
}

function resetUiState(msg) {
  setLock(false);
  setVerified(false);
  S.lockedMelbetId = null;
  S.detectedMelbetId = null;
  S.activeEntityId = null;
  S.selectedEntityId = null;
  S.selectedFormat = null;
  S.selectedFixture = null;
  S.mulling = { delivery: false, batsman: false, wicket: false };
  $("matchKey").value = "";
  $("entityKey").value = "";
  $("type").value = "";
  $("matchUrl").value = "";
  if ($("status")) $("status").textContent = msg || "Waiting for data...";
  if ($("matchTeams")) $("matchTeams").textContent = "-- vs --";
  if ($("score")) $("score").textContent = "0 - 0";
  if ($("overTxt")) $("overTxt").textContent = "0.0 OVER";
  if ($("overNo")) $("overNo").textContent = "-- OVER";
  S.currentOver = null;
  S.overDots = [];
  renderOverDots();
  setBall("idle", "-");
  document.querySelectorAll("input.radio-look[data-kind]").forEach(cb => {
    cb.checked = false;
    const t = $(cb.dataset.target);
    if (t) t.hidden = true;
  });
}

function handleEntityBallEvent(m, isSnapshot = false) {
  const p = classifyEventText(m.event);
  setBall(p.kind, p.label);
  $("status").textContent = isSnapshot ? "Preview • last known" : "Entity Push • Live";
  if (!isSnapshot) {
    const now = Date.now();
    if (S.lastEventAt) updateClickBar(Math.min(300, now - S.lastEventAt));
    S.lastEventAt = now;
  }
  if (m.over_number != null) {
    $("overTxt").textContent = `${m.over_number}.${m.ball_number || 0} OVER`;
    $("overNo").textContent = `OVER ${m.over_number}`;
  }
  if (m.score) $("score").textContent = m.score;
  if (m.teams) $("matchTeams").textContent = m.teams;
  updateOverDots(m.over_number, m.ball_number, p.kind);
  if (m.lag_ms != null) updateOddsBar(m.lag_ms);
  if (!isSnapshot) {
    log(`[Ball] ${m.over_number ?? "?"}.${m.ball_number ?? "?"} ${m.event || "-"} ${m.lag_ms != null ? `(lag=${m.lag_ms}ms)` : ""}`);
  }
}

function applySnapshot(m) {
  S.currentOver = null;
  S.overDots = [];
  renderOverDots();
  setBall("idle", "-");
  $("status").textContent = "Preview • waiting for data...";
  $("matchTeams").textContent = m.teams || "-- vs --";
  $("score").textContent = m.score || "0 - 0";
  $("overTxt").textContent = "0.0 OVER";
  $("overNo").textContent = "-- OVER";
  if (m.event) {
    handleEntityBallEvent({
      ...m.event,
      teams: m.teams || m.event.teams,
      score: m.score || m.event.score,
    }, true);
  }
}

function setMulling(kind, on) {
  S.mulling[kind] = on;
  const cb = $(kind);
  if (cb) {
    cb.checked = on;
    const t = $(cb.dataset.target);
    if (t) t.hidden = !on;
  }
}

/* ---------- WebSocket ---------- */
function startLiveListener() {
  S.ws = new WebSocket(WS_URL);
  S.ws.onopen = () => log("# WebSocket connected");
  S.ws.onmessage = (ev) => {
    let m;
    try { m = JSON.parse(ev.data); } catch { return; }
    switch (m.type) {
      case "entity_push_status":
        setEntityStatus(m.status, m.messages);
        break;

      case "guard_status":
        setGuard(m.killed);
        break;

      case "stake_update":
        if (m.stake) {
          S.stake = m.stake;
          const inp = $("stakeInput");
          if (inp) inp.value = m.stake;
          updateStakeButtons(m.stake);
          log(`# Stake = ${m.stake}`);
        }
        break;

      case "browser_status":
        if (!m.main) {
          S.isLocked = false;
          S.lockedMelbetId = null;
          S.detectedMelbetId = null;
          S.activeEntityId = null;
          $("matchKey").value = "";
        } else if (m.match_key) {
          S.detectedMelbetId = m.match_key;
          $("matchKey").value = m.match_key;
        }
        if (m.locked) setLock(true);
        if (m.verified) setVerified(true);
        if (m.entity_key) {
          S.activeEntityId = m.entity_key;
          $("entityKey").value = m.entity_key;
        }
        S.workerLaunched.batsman = !!m.batsman;
        S.workerLaunched.wicket = !!m.wicket;
        break;

      case "browser_closed":
        if (m.target === "main") {
          resetUiState("Browser closed");
          log(`# ⚠️ Main browser closed — UI reset`, true);
        } else {
          S.workerLaunched[m.target] = false;
          S.mulling[m.target] = false;
          log(`# ⚠️ ${m.target} browser closed`, true);
        }
        break;

      case "entity_active_match":
        S.activeEntityId = m.match_id;
        if (m.match_id) log(`# ✅ Active: entity=${m.match_id} melbet=${m.melbet_match_id}`);
        break;

      case "match_id_detected":
        S.detectedMelbetId = m.match_id;
        if (!S.isLocked) $("matchKey").value = m.match_id;
        log(`# 🎯 Melbet match ${m.locked ? "(locked)" : "detected"}: ${m.match_id}`);
        break;

      case "verified":
        setVerified(true);
        log(`# ✅ Verified → melbet=${m.match_id} entity=${m.entity_match_id}`);
        break;

      case "unlocked":
        setLock(false);
        S.lockedMelbetId = null;
        $("matchKey").value = S.detectedMelbetId || "";
        break;

      case "entity_match_info":
        if (m.teams) $("matchTeams").textContent = m.teams;
        break;

      case "entity_snapshot":
        applySnapshot(m);
        break;

      case "entity_ball_event":
        handleEntityBallEvent(m);
        break;

      case "mulling_status":
        setMulling(m.worker, !!m.enabled);
        break;

      case "worker_error":
        log(`# ⚠️ ${m.worker} error: ${m.message}`, true);
        break;

      case "match_update":
        if (m.teams) $("matchTeams").textContent = m.teams;
        if (m.score) $("score").textContent = m.score;
        if (m.over) $("overTxt").textContent = `${m.over} OVER`;
        if (m.overNo) $("overNo").textContent = m.overNo;
        if (m.status) $("status").textContent = m.status;
        if (m.ball) setBall(m.ballKind || "run", m.ball);
        break;
    }
  };
  S.ws.onclose = () => {
    log("# WebSocket disconnected, retrying in 3s...", true);
    setEntityStatus("disconnected");
    setTimeout(startLiveListener, 3000);
  };
  S.ws.onerror = () => {};
}

/* ---------- Fixtures ---------- */
async function loadFixtures() {
  const tb = $("fixture");
  if (!tb) return;
  tb.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">Loading fixtures...</td></tr>`;
  try {
    const res = await fetch(`${API_BASE}/api/fixtures`);
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `HTTP ${res.status}`);
    const data = await res.json();
    const fixtures = data.fixtures || [];
    if (!fixtures.length) {
      tb.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">No fixtures</td></tr>`;
      return;
    }
    let h = "";
    fixtures.forEach(f => {
      const color =
        /live|started/i.test(f.status) ? "var(--green)" :
        /upcoming|not started/i.test(f.status) ? "var(--yellow)" :
        "var(--text-muted)";
      h += `<tr style="cursor:pointer"
        data-key="${escapeHtml(f.match_id)}"
        data-title="${escapeHtml(f.title || "")}"
        data-type="${escapeHtml(f.format || "")}"
        data-status="${escapeHtml(f.status || "")}">
        <td><code>${escapeHtml(f.match_id)}</code></td>
        <td><strong>${escapeHtml(f.title)}</strong></td>
        <td>${escapeHtml(f.format || "—")}</td>
        <td><span style="color:${color}">${escapeHtml((f.status || "").toUpperCase())}</span></td>
      </tr>`;
    });
    tb.innerHTML = h;
    tb.querySelectorAll("tr").forEach(tr => {
      tr.addEventListener("click", () => {
        tb.querySelectorAll("tr").forEach(r => r.classList.remove("selected"));
        tr.classList.add("selected");
        S.selectedEntityId = tr.dataset.key;
        S.selectedFormat = tr.dataset.type;
        S.selectedFixture = { title: tr.dataset.title, format: tr.dataset.type, status: tr.dataset.status };
        $("entityKey").value = tr.dataset.key;
        $("type").value = tr.dataset.type;
        log(`# Fixture selected: ${tr.dataset.title} (entity=${tr.dataset.key}, format=${tr.dataset.type})`);
        postJson("/api/preview", { entity_match_id: tr.dataset.key });
      });
    });
  } catch (e) {
    tb.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--red)">Failed: ${escapeHtml(e.message)}</td></tr>`;
    log(`# Fixture load failed: ${e.message}`, true);
  }
}

/* ---------- DOM ready ---------- */
window.addEventListener("DOMContentLoaded", () => {
  startLiveListener();
  loadFixtures();
  loadStake();
  setInterval(loadStake, 30000);
  updateClickBar(0);
  updateOddsBar(0);
  setLock(false);

  $("refreshFixtures").addEventListener("click", loadFixtures);

  async function launchMain() {
    const url = $("site").value.trim();
    if (!url) return log("# Website URL required", true);
    log(`# Launching main browser: ${url}`);
    const res = await postJson("/api/launch", { website_url: url });
    if (res?.status === "success") {
      log(`# ✅ ${res.message || "Browser opened"}`);
    } else {
      log(`# ❌ ${res?.message || "Launch failed"}`, true);
    }
  }
  $("submitSiteBtn").addEventListener("click", launchMain);
  $("bLaunch").addEventListener("click", launchMain);

  /* ---------- Stake wiring ---------- */
  $("applyStakeBtn").addEventListener("click", () => applyStake($("stakeInput").value));
  $("stakeInput").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      applyStake($("stakeInput").value);
    }
  });
  document.querySelectorAll(".stake-preset").forEach(btn => {
    btn.addEventListener("click", () => applyStake(btn.dataset.stake));
  });

  $("bStop").addEventListener("click", async () => {
    log("# Stop requested — disarming all workers…");
    await postJson("/api/stop-all", {});
    location.reload();
  });

  $("bKill").addEventListener("click", async () => {
    const res = await postJson(S.guardKilled ? "/api/guard/resume" : "/api/guard/kill", {});
    if (res?.status === "success") {
      log(`# ${res.message}`, !S.guardKilled);
    } else {
      log(`# ❌ ${res?.message || "Kill-switch request failed"}`, true);
    }
  });

  let parseTimer = null;
  $("matchUrl").addEventListener("input", () => {
    clearTimeout(parseTimer);
    parseTimer = setTimeout(async () => {
      if (S.isLocked) return;
      const url = $("matchUrl").value.trim();
      if (!url) return;
      const res = await postJson("/api/parse-match-url", { url });
      if (res?.status === "success") {
        $("matchKey").value = res.match_id;
        log(`# Match URL থেকে ম্যাচ আইডি: ${res.match_id}`);
      }
    }, 400);
  });

  $("lockBtn").addEventListener("click", async () => {
    if (!S.isLocked) {
      const mid = ($("matchKey").value || "").trim();
      if (!mid) return log("# Open a match in browser first — no match ID detected", true);
      const res = await postJson("/api/lock", { match_id: mid });
      if (res?.status === "success") {
        S.lockedMelbetId = res.match_id;
        setLock(true);
        log(`# 🔒 Locked: ${res.match_id}`);
      } else {
        log(`# ❌ ${res?.message || "Lock failed"}`, true);
      }
    } else {
      const res = await postJson("/api/unlock", {});
      if (res?.status === "success") {
        setLock(false);
        log("# Match unlocked");
      }
    }
  });

  $("verifyBtn").addEventListener("click", async () => {
    if (S.isVerified) return;
    const url = $("matchUrl").value.trim();
    if (!url) return log("# Match URL required", true);
    if (!S.isLocked) return log("# Lock a match first", true);
    if (!S.selectedEntityId) return log("# Select a fixture first", true);
    if (!S.selectedFormat) return log("# Match format missing", true);
    const mid = ($("matchKey").value || "").trim();
    if (!mid) return log("# Melbet match ID missing", true);

    log("# Verifying match URL…");
    const res = await postJson("/api/verify-match-url", {
      url,
      match_id: mid,
      entity_match_id: S.selectedEntityId,
      format: S.selectedFormat,
      title: S.selectedFixture?.title || "",
    });
    if (res?.status === "success") {
      setVerified(true);
      log(`# ✅ Verified → melbet=${res.match_id} entity=${res.entity_match_id}`);
    } else {
      log(`# ❌ ${res?.message || "Verify failed"}`, true);
    }
  });

  document.querySelectorAll("input.radio-look[data-kind]").forEach(cb => {
    cb.addEventListener("change", async () => {
      const kind = cb.dataset.kind;
      const target = $(cb.dataset.target);
      if (!cb.checked) {
        if (target) target.hidden = true;
        return;
      }

      document.querySelectorAll("input.radio-look[data-kind]").forEach(o => {
        if (o !== cb) {
          o.checked = false;
          const t = $(o.dataset.target);
          if (t) t.hidden = true;
        }
      });

      if (kind === "batsman" || kind === "wicket") {
        if (!S.workerLaunched[kind]) {
          const url = $("site").value.trim();
          if (!url) { cb.checked = false; return log("# Website URL required", true); }
          log(`# Launching ${kind} browser (separate profile)…`);
          const res = await postJson(`/api/launch-worker/${kind}`, { website_url: url });
          if (res?.status === "success") {
            S.workerLaunched[kind] = true;
            log(`# ✅ ${kind} browser opened — login + open verified match URL manually`);
            if (target) target.hidden = false;
          } else {
            cb.checked = false;
            log(`# ❌ ${kind} launch failed: ${res?.message}`, true);
          }
        } else {
          if (target) target.hidden = false;
        }
      } else {
        if (target) target.hidden = false;
      }
    });
  });

  document.querySelectorAll(".mulling-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const kind = btn.dataset.kind;
      const wanted = !S.mulling[kind];
      if (wanted) {
        if (S.guardKilled) return log("# Kill-switch ON — আগে Resume করুন", true);
        if (!S.isVerified) return log("# Verify a match first", true);
        if (!S.activeEntityId) return log("# No active entity match", true);
        if ((kind === "batsman" || kind === "wicket") && !S.workerLaunched[kind])
          return log(`# Open ${kind} browser first (click checkbox)`, true);
      }
      log(`# ${kind} mulling → ${wanted ? "ON" : "OFF"}…`);
      const res = await postJson(`/api/mulling/${kind}`, { enabled: wanted });
      if (res?.status === "success") {
        setMulling(kind, wanted);
        log(`# ✅ ${res.message}`);
      } else {
        log(`# ❌ ${res?.message || "Mulling failed"}`, true);
      }
    });
  });

  document.querySelectorAll(".btns .stop").forEach(btn => {
    btn.addEventListener("click", async () => {
      const kind = btn.dataset.kind;
      if (!kind || !S.mulling[kind]) return;
      const res = await postJson(`/api/mulling/${kind}`, { enabled: false });
      if (res?.status === "success") {
        setMulling(kind, false);
        log(`# ${kind} mulling stopped`);
      }
    });
  });
});