// =====================================================================
// scripts.js — Space Pathfinders client
// Kết nối Socket.IO thật để nhiều người ở nhiều máy/nơi khác nhau cùng
// chơi trong 1 phòng. Toàn bộ hành động (roll, mua đồ, rút bài, chọn
// hướng...) đi qua socket và nhận state mới ngay lập tức.
// =====================================================================

const CHARACTERS = {
  THO:       { id: "THO",       name: "Trang - Thỏ Vũ Trụ",      emoji: "🐰", color: "#FF819C" },
  CANH_CUT:  { id: "CANH_CUT",  name: "Quang - Cánh Cụt Du Hành", emoji: "🐧", color: "#66C7F4" },
  CAO:       { id: "CAO",       name: "Thành - Cáo Phi Hành",     emoji: "🦊", color: "#FFB8E3" },
  QUA:       { id: "QUA",       name: "Jin - Quạ Không Gian",     emoji: "🐦‍⬛", color: "#6C6EA0" },
};
const CHAR_ORDER = ["THO", "CANH_CUT", "CAO", "QUA"];

const TILE_ICONS = {
  TRONG: "⬜", VANG: "💰", DO: "☄️", XANH: "🌀", TIM: "🔮", CAM: "🪤", HONG: "🚪", DICH: "🏁",
};
const TILE_NAMES = {
  TRONG: "Ô Trống", VANG: "Ô Vàng", DO: "Ô Đỏ", XANH: "Cổng Dịch Chuyển",
  TIM: "Ô Sự Kiện", CAM: "Ô Bẫy", HONG: "Cổng Thu Phí", DICH: "ĐÍCH",
};

// ---------------------------------------------------------------------
// STATE CỤC BỘ CỦA CLIENT
// ---------------------------------------------------------------------
let socket = null;
let myPlayerId = null;
let myRoomCode = null;
let selectedCharacter = null;
let currentTab = "create";
let latestState = null;
let previousPositions = {};   // playerId -> vị trí trước đó (để animate di chuyển)
let tilePositions = null;     // cache toạ độ 100 ô (không đổi trong 1 ván)
let seenEventIds = new Set(); // event popup đã hiển thị rồi (tránh hiện lại)
let pendingSelection = {};    // lựa chọn tạm cho modal chọn nhiều bước (2 mục tiêu...)
let cardQueue = [];           // hàng đợi hiệu ứng lật bài (tránh chồng nhiều bài cùng lúc)
let cardAnimating = false;

// =====================================================================
// STARFIELD NỀN
// =====================================================================
(function initStarfield() {
  const canvas = document.getElementById("starfield");
  const ctx = canvas.getContext("2d");
  let stars = [];
  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const count = Math.floor((canvas.width * canvas.height) / 4500);
    stars = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.4 + 0.2,
      speed: Math.random() * 0.15 + 0.02,
      twinkle: Math.random() * Math.PI * 2,
    }));
  }
  function tick() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const s of stars) {
      s.twinkle += 0.02;
      const alpha = 0.5 + 0.5 * Math.sin(s.twinkle);
      ctx.fillStyle = `rgba(244,246,255,${alpha})`;
      ctx.beginPath();
      ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
      ctx.fill();
      s.y += s.speed;
      if (s.y > canvas.height) { s.y = 0; s.x = Math.random() * canvas.width; }
    }
    requestAnimationFrame(tick);
  }
  window.addEventListener("resize", resize);
  resize();
  tick();
})();

// =====================================================================
// TIỆN ÍCH CHUNG
// =====================================================================
function $(sel) { return document.querySelector(sel); }
function $all(sel) { return Array.from(document.querySelectorAll(sel)); }
function showScreen(id) {
  $all(".screen").forEach(s => s.classList.add("hidden"));
  $(id).classList.remove("hidden");
}
function findPlayer(state, id) { return state.players.find(p => p.id === id); }
function charOf(player) { return CHARACTERS[player.character] || { emoji: "👤", name: player.name }; }

// =====================================================================
// MÀN HÌNH THIẾT LẬP (tạo / vào phòng + chọn nhân vật)
// =====================================================================
function buildCharGrid(containerId, takenList = []) {
  const grid = $(containerId);
  grid.innerHTML = "";
  CHAR_ORDER.forEach(cid => {
    const c = CHARACTERS[cid];
    const taken = takenList.includes(cid);
    const div = document.createElement("div");
    div.className = "char-card" + (taken ? " taken" : "") + (selectedCharacter === cid ? " selected" : "");
    div.innerHTML = `<span class="char-emoji">${c.emoji}</span><span class="char-name">${c.name}</span>`;
    if (!taken) {
      div.addEventListener("click", () => {
        selectedCharacter = cid;
        buildCharGrid(containerId, takenList);
        validateSetupForm();
      });
    }
    grid.appendChild(div);
  });
}

function validateSetupForm() {
  const btn = $("#btn-submit-setup");
  if (currentTab === "create") {
    const name = $("#create-name").value.trim();
    btn.disabled = !(name && selectedCharacter);
  } else {
    const name = $("#join-name").value.trim();
    const code = $("#join-code").value.trim();
    btn.disabled = !(name && code.length === 5 && selectedCharacter);
  }
}

$all(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    currentTab = btn.dataset.tab;
    $all(".tab-btn").forEach(b => b.classList.toggle("active", b === btn));
    $all(".tab-panel").forEach(p => p.classList.remove("active"));
    $(`#tab-${currentTab}`).classList.add("active");
    selectedCharacter = null;
    buildCharGrid("#char-grid");
    validateSetupForm();
  });
});
$("#create-name").addEventListener("input", validateSetupForm);
$("#join-name").addEventListener("input", validateSetupForm);

let joinPeekTimer = null;
$("#join-code").addEventListener("input", (e) => {
  e.target.value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 5);
  validateSetupForm();
  clearTimeout(joinPeekTimer);
  joinPeekTimer = setTimeout(peekRoomForTakenChars, 400);
});

async function peekRoomForTakenChars() {
  const code = $("#join-code").value.trim();
  if (code.length !== 5) return;
  try {
    const res = await fetch(`/api/state/${code}`);
    const data = await res.json();
    if (data.success) {
      const taken = data.state.players.map(p => p.character);
      buildCharGrid("#char-grid", taken);
    }
  } catch (e) { /* phòng chưa tồn tại, bỏ qua */ }
}

buildCharGrid("#char-grid");

$("#btn-submit-setup").addEventListener("click", async () => {
  const errEl = $("#setup-error");
  errEl.textContent = "";
  try {
    if (currentTab === "create") {
      const name = $("#create-name").value.trim();
      const res = await fetch("/api/create_room", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, character: selectedCharacter }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      myRoomCode = data.state.room_code;
      myPlayerId = data.state.players[0].id;
      enterRoom(data.state);
    } else {
      const name = $("#join-name").value.trim();
      const code = $("#join-code").value.trim();
      const res = await fetch("/api/join_room", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_code: code, name, character: selectedCharacter }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      myRoomCode = data.state.room_code;
      const me = data.state.players.find(p => p.name === name && p.character === selectedCharacter);
      myPlayerId = me ? me.id : data.state.players[data.state.players.length - 1].id;
      enterRoom(data.state);
    }
  } catch (e) {
    errEl.textContent = e.message || "Có lỗi xảy ra.";
  }
});

function enterRoom(state) {
  socket = io();
  socket.on("connect", () => {
    socket.emit("join", { room_code: myRoomCode, player_id: myPlayerId });
  });
  socket.on("lobby_update", (data) => { if (data.success) onStateUpdate(data.state); });
  socket.on("state_update", (data) => { if (data.success) onStateUpdate(data.state); });
  socket.on("action_error", (data) => flashPopup("⚠️", data.error || "Hành động không hợp lệ"));
  onStateUpdate(state);
}

// =====================================================================
// PHÒNG CHỜ (LOBBY)
// =====================================================================
function renderLobby(state) {
  $("#lobby-code").textContent = state.room_code;
  const list = $("#lobby-players");
  list.innerHTML = "";
  state.players.forEach((p, idx) => {
    const c = CHARACTERS[p.character] || {};
    const row = document.createElement("div");
    row.className = "lobby-player-row" + (idx === 0 ? " host" : "") + (p.connected ? "" : " offline");
    row.innerHTML = `<span class="lp-emoji">${c.emoji || "👤"}</span>
      <span class="lp-name">${p.name}</span>
      <span class="lp-status">${p.connected ? "SẴN SÀNG" : "MẤT KẾT NỐI"}</span>`;
    list.appendChild(row);
  });
  const isHost = state.players.length && state.players[0].id === myPlayerId;
  const startBtn = $("#btn-start-game");
  startBtn.classList.toggle("hidden", !isHost);
  startBtn.disabled = state.players.length < 2;
  $("#lobby-hint").textContent = isHost
    ? (state.players.length < 2 ? "Cần tối thiểu 2 phi hành gia để bắt đầu." : "Sẵn sàng! Nhấn nút để phóng tàu.")
    : "Đang chờ chủ phòng bắt đầu ván đấu...";
}

$("#btn-start-game").addEventListener("click", () => {
  socket.emit("start_game", { room_code: myRoomCode, player_id: myPlayerId });
});

// =====================================================================
// XỬ LÝ STATE MỚI TỪ SERVER
// =====================================================================
function onStateUpdate(state) {
  const prev = latestState;
  latestState = state;

  if (!state.game_started) {
    showScreen("#screen-lobby");
    renderLobby(state);
    return;
  }

  if (!prev || !prev.game_started) {
    // vừa mới bắt đầu ván — khởi tạo vị trí ban đầu để không bị "warp" giả
    state.players.forEach(p => { previousPositions[p.id] = p.position; });
    showScreen("#screen-game");
  }

  processNewEvents(state);
  renderHud(state);
  renderCrew(state);
  renderLog(state);
  renderBoardAndTokens(state);
  renderItemBar(state);
  renderPendingModals(state);

  // cập nhật vị trí đã biết SAU khi animation đã dùng vị trí cũ để tính toán
  state.players.forEach(p => { previousPositions[p.id] = p.position; });
}

// =====================================================================
// HUD TRÊN CÙNG
// =====================================================================
let timerInterval = null;
function renderHud(state) {
  $("#hud-room-code").textContent = state.room_code;
  $("#hud-turn").textContent = state.turn_count;
  $("#hud-fund").textContent = state.common_fund;

  clearInterval(timerInterval);
  const updateTimer = () => {
    const elapsed = Date.now() / 1000 - state.started_at;
    const remaining = Math.max(0, Math.round(state.time_limit_seconds - elapsed));
    const mm = String(Math.floor(remaining / 60)).padStart(2, "0");
    const ss = String(remaining % 60).padStart(2, "0");
    $("#hud-timer").textContent = `${mm}:${ss}`;
  };
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);

  const cur = state.players[state.current_player_index];
  if (cur) {
    const c = charOf(cur);
    $("#turn-banner").innerHTML = cur.id === myPlayerId
      ? `Lượt của bạn — <b>${c.emoji} ${cur.name}</b>`
      : `Lượt của <b>${c.emoji} ${cur.name}</b>`;
  }
}

$("#btn-open-guide").addEventListener("click", () => $("#modal-guide").classList.remove("hidden"));
$("#btn-close-guide").addEventListener("click", () => $("#modal-guide").classList.add("hidden"));

// =====================================================================
// CREW PANEL
// =====================================================================
function renderCrew(state) {
  const list = $("#crew-list");
  list.innerHTML = "";
  state.players.forEach((p, idx) => {
    const c = CHARACTERS[p.character] || {};
    const active = idx === state.current_player_index && !p.finished;
    const div = document.createElement("div");
    div.className = "crew-card" + (active ? " active" : "") + (p.finished ? " finished" : "");
    const badges = p.items.map(it => (state.item_info[it]?.emoji || "❔")).join(" ");
    div.innerHTML = `
      <div class="cc-name"><span class="crew-dot" style="color:${c.color}"></span>${c.emoji} ${p.name}${p.id === myPlayerId ? " (Bạn)" : ""}</div>
      <div class="cc-row"><span>Ô ${p.position}</span><span>💰 ${p.gold}${p.debt > 0 ? ` (nợ ${p.debt})` : ""}</span></div>
      <div class="cc-badges">${badges}${p.shield_charges > 0 ? " 🛡️".repeat(p.shield_charges) : ""}${!p.connected ? " 🔌" : ""}</div>
    `;
    list.appendChild(div);
  });
}

// =====================================================================
// LOG PANEL
// =====================================================================
function renderLog(state) {
  const list = $("#log-list");
  list.innerHTML = "";
  [...state.log].reverse().forEach(line => {
    const d = document.createElement("div");
    d.textContent = line;
    list.appendChild(d);
  });
}

// =====================================================================
// BÀN CỜ MÊ CUNG + CAMERA THEO NGƯỜI CHƠI + TOKEN DI CHUYỂN TỪNG BƯỚC
// =====================================================================
function computeTilePositions(board) {
  const colW = 200, rowH = 130, padX = 100, padY = 100;
  const pos = {};
  board.forEach(tile => {
    const i = tile.index;
    const r = Math.floor((i - 1) / 10);
    const p = (i - 1) % 10;
    const x = (r % 2 === 0) ? p * colW : (9 - p) * colW;
    const y = (9 - r) * rowH;
    pos[i] = { x: padX + x, y: padY + y };
  });
  return pos;
}

function renderBoardAndTokens(state) {
  if (!tilePositions) tilePositions = computeTilePositions(state.board);
  const track = $("#board-track");

  // Chỉ build lại toàn bộ ô nếu chưa từng build (vị trí cố định, chỉ đổi type/board data)
  if (track.children.length === 0) {
    let html = "";
    // đường nối (path lines) - vẽ trước để nằm dưới ô
    state.board.forEach(tile => {
      const from = tilePositions[tile.index];
      (tile.connections || []).forEach(target => {
        const to = tilePositions[target];
        if (!to) return;
        const dx = (to.x - from.x), dy = (to.y - from.y);
        const len = Math.sqrt(dx * dx + dy * dy);
        const angle = Math.atan2(dy, dx) * 180 / Math.PI;
        const isBranch = tile.connections.length > 1;
        html += `<div class="tile-path-line" style="
          left:${from.x + 46}px; top:${from.y + 46}px; width:${len}px;
          transform: rotate(${angle}deg);
          ${isBranch ? "background: rgba(255,209,102,0.55);" : ""}
        "></div>`;
      });
    });
    track.innerHTML = html;

    state.board.forEach(tile => {
      const p = tilePositions[tile.index];
      const div = document.createElement("div");
      div.id = `tile-${tile.index}`;
      div.className = `tile tile-${tile.type}` + (tile.is_branch ? " is-branch" : "");
      div.style.left = p.x + "px";
      div.style.top = p.y + "px";
      div.innerHTML = `<span class="tile-index">${tile.index}</span><span class="tile-icon">${TILE_ICONS[tile.type]}</span>`;
      div.title = `${TILE_NAMES[tile.type]}${tile.is_branch ? " — Ngã ba!" : ""}`;
      track.appendChild(div);
    });
  } else {
    // cập nhật lại màu/loại ô nếu bài Bẫy đã tráo đổi loại ô
    state.board.forEach(tile => {
      const div = $(`#tile-${tile.index}`);
      if (!div) return;
      div.className = `tile tile-${tile.type}` + (tile.is_branch ? " is-branch" : "");
      div.querySelector(".tile-icon").textContent = TILE_ICONS[tile.type];
      div.title = `${TILE_NAMES[tile.type]}${tile.is_branch ? " — Ngã ba!" : ""}`;
    });
  }

  renderTokens(state);
  updateCamera(state);
}

function tileCenter(idx) {
  const p = tilePositions[idx];
  return { x: p.x + 46, y: p.y + 46 };
}

// Đi theo đúng đồ thị (connections) từ vị trí cũ tới vị trí mới, để animate
// từng bước thay vì "tele" thẳng tới ô đích. Nếu không đi được (VD: cổng
// dịch chuyển / thẻ dịch chuyển ô) thì trả về null -> sẽ dùng hiệu ứng warp.
function findStepPath(board, fromIdx, toIdx, maxSteps = 16) {
  if (fromIdx === toIdx) return [fromIdx];
  let path = [fromIdx];
  let cur = fromIdx;
  for (let i = 0; i < maxSteps; i++) {
    const tile = board.find(t => t.index === cur);
    if (!tile || !tile.connections || tile.connections.length === 0) return null;
    // ưu tiên hướng dẫn tới đích nếu là 1 trong các lựa chọn ngã ba
    const next = tile.connections.includes(toIdx) ? toIdx : tile.connections[0];
    path.push(next);
    cur = next;
    if (cur === toIdx) return path;
  }
  return null;
}

let tokenAnimTimers = {};
function renderTokens(state) {
  const layer = $("#tokens-layer");

  state.players.forEach((p, idx) => {
    let el = document.getElementById(`token-${p.id}`);
    if (!el) {
      el = document.createElement("div");
      el.id = `token-${p.id}`;
      el.className = "player-token";
      el.style.borderColor = charOf(p).color || "var(--cyan)";
      const c = tileCenter(previousPositions[p.id] ?? p.position);
      el.style.left = (c.x - 20 + idx * 4) + "px";
      el.style.top = (c.y - 20 + idx * 4) + "px";
      el.innerHTML = `<span>${charOf(p).emoji}</span>`;
      layer.appendChild(el);
    }

    const oldPos = previousPositions[p.id];
    const newPos = p.position;
    if (oldPos === undefined || oldPos === newPos) return;

    clearTimeout(tokenAnimTimers[p.id]);
    const path = findStepPath(state.board, oldPos, newPos);

    if (path && path.length > 1) {
      // Di chuyển từng ô một, có độ trễ giữa mỗi bước — thấy rõ từng bước đi
      let step = 1;
      const stepFn = () => {
        if (step >= path.length) return;
        const c = tileCenter(path[step]);
        el.classList.add("moving");
        el.style.left = (c.x - 20 + idx * 4) + "px";
        el.style.top = (c.y - 20 + idx * 4) + "px";
        setTimeout(() => el.classList.remove("moving"), 260);
        step++;
        tokenAnimTimers[p.id] = setTimeout(stepFn, 320);
      };
      stepFn();
    } else {
      // Không đi theo đường thường được (dịch chuyển / thẻ) -> hiệu ứng warp
      el.style.transition = "none";
      el.style.opacity = "0";
      setTimeout(() => {
        const c = tileCenter(newPos);
        el.style.left = (c.x - 20 + idx * 4) + "px";
        el.style.top = (c.y - 20 + idx * 4) + "px";
        el.style.transition = "";
        el.style.opacity = "1";
        el.classList.add("moving");
        setTimeout(() => el.classList.remove("moving"), 400);
      }, 180);
    }
  });
}

function updateCamera(state) {
  const cur = state.players[state.current_player_index];
  if (!cur) return;
  const frame = $(".viewport-frame");
  const rect = frame.getBoundingClientRect();
  const c = tileCenter(cur.position);
  const camera = $("#board-camera");
  const tx = rect.width / 2 - c.x;
  const ty = rect.height / 2 - c.y;
  camera.style.transform = `translate(${tx}px, ${ty}px)`;
}
window.addEventListener("resize", () => { if (latestState) updateCamera(latestState); });

// =====================================================================
// XÚC XẮC (roulette orb)
// =====================================================================
$("#btn-roll").addEventListener("click", () => {
  if (!latestState) return;
  const cur = latestState.players[latestState.current_player_index];
  if (!cur || cur.id !== myPlayerId) return;
  const orb = $("#dice-orb");
  const face = $("#dice-orb-face");
  orb.classList.remove("landed");
  orb.classList.add("spinning");
  let spins = 0;
  const spinFace = setInterval(() => { face.textContent = "🎲🌀✨🔮"[spins++ % 4]; }, 90);
  setTimeout(() => clearInterval(spinFace), 1000);
  socket.emit("roll_dice", { room_code: myRoomCode, player_id: myPlayerId });
});

function updateRollButtonState(state) {
  const cur = state.players[state.current_player_index];
  const btn = $("#btn-roll");
  const canRoll = cur && cur.id === myPlayerId && !state.pending_action && !state.pending_shop_tile && !state.pending_move && !state.game_over;
  btn.disabled = !canRoll;
  btn.textContent = canRoll ? "PHÓNG PHI TIÊU MAY MẮN" : (state.game_over ? "VÁN ĐẤU ĐÃ KẾT THÚC" : "ĐANG CHỜ...");
}

// =====================================================================
// VẬT PHẨM
// =====================================================================
function renderItemBar(state) {
  const bar = $("#item-bar");
  bar.innerHTML = "";
  const me = findPlayer(state, myPlayerId);
  updateRollButtonState(state);
  if (!me || me.items.length === 0) return;
  const canUse = state.players[state.current_player_index].id === myPlayerId
    && !state.pending_action && !state.pending_shop_tile && !state.pending_move && !state.game_over;
  me.items.forEach(item => {
    const info = state.item_info[item];
    const chip = document.createElement("div");
    chip.className = "item-chip";
    chip.innerHTML = `<span>${info.emoji} ${info.name}</span>`;
    const btn = document.createElement("button");
    btn.textContent = "DÙNG";
    btn.disabled = !canUse;
    btn.addEventListener("click", () => useItemFlow(item, state));
    chip.appendChild(btn);
    bar.appendChild(chip);
  });
}

function useItemFlow(item, state) {
  if (item === "DAO_GAM") {
    const me = findPlayer(state, myPlayerId);
    const targets = state.players.filter(p => p.id !== myPlayerId && !p.finished && Math.abs(p.position - me.position) <= 3);
    if (targets.length === 0) { flashPopup("🔫", "Không có mục tiêu nào trong bán kính 3 ô!"); return; }
    openChoiceModal("CHỌN MỤC TIÊU", "Bắn Tia Đẩy Lực vào ai?", targets.map(t => ({
      label: `${charOf(t).emoji} ${t.name} (ô ${t.position})`,
      onClick: () => socket.emit("use_item", { room_code: myRoomCode, player_id: myPlayerId, item_type: item, target_id: t.id }),
    })));
  } else if (item === "KINH_AP_TRONG") {
    openChoiceModal("KÍNH ĐỊNH VỊ 3 MẮT", "Chỉnh xúc xắc lượt tới:", [
      { label: "+1", onClick: () => socket.emit("use_item", { room_code: myRoomCode, player_id: myPlayerId, item_type: item, delta: 1 }) },
      { label: "-1", onClick: () => socket.emit("use_item", { room_code: myRoomCode, player_id: myPlayerId, item_type: item, delta: -1 }) },
    ]);
  } else {
    socket.emit("use_item", { room_code: myRoomCode, player_id: myPlayerId, item_type: item });
  }
}

function openChoiceModal(title, desc, buttons) {
  $("#pending-title").textContent = title;
  $("#pending-desc").textContent = desc;
  const opt = $("#pending-options");
  opt.innerHTML = "";
  buttons.forEach(b => {
    const btn = document.createElement("button");
    btn.textContent = b.label;
    btn.addEventListener("click", () => { $("#modal-pending").classList.add("hidden"); b.onClick(); });
    opt.appendChild(btn);
  });
  $("#modal-pending").classList.remove("hidden");
}

// =====================================================================
// CỬA HÀNG CỦA GÃ HỀ
// =====================================================================
function renderShop(state) {
  const me = findPlayer(state, myPlayerId);
  const isMe = state.players[state.current_player_index].id === myPlayerId;
  if (!isMe) { $("#modal-shop").classList.add("hidden"); return; }

  const wrap = $("#shop-items");
  wrap.innerHTML = "";
  Object.entries(state.item_info).forEach(([key, info]) => {
    const stock = state.item_stock[key] ?? 0;
    const canBuy = stock > 0 && me.items.length < 2 && me.gold >= info.price;
    const row = document.createElement("div");
    row.className = "shop-item";
    row.innerHTML = `
      <div>
        <div class="si-name">${info.emoji} ${info.name}</div>
        <div class="si-info">${info.desc} · Giá ${info.price} vàng · Còn ${stock}</div>
      </div>`;
    const btn = document.createElement("button");
    btn.textContent = "MUA";
    btn.disabled = !canBuy;
    btn.addEventListener("click", () => socket.emit("buy_item", { room_code: myRoomCode, player_id: myPlayerId, item_type: key }));
    row.appendChild(btn);
    wrap.appendChild(row);
  });
  $("#modal-shop").classList.remove("hidden");
}
$("#btn-skip-shop").addEventListener("click", () => {
  socket.emit("skip_shop", { room_code: myRoomCode, player_id: myPlayerId });
});

// =====================================================================
// MODAL HÀNH ĐỘNG CHỜ (ngã ba / bài sự kiện cần chọn mục tiêu, ô...)
// =====================================================================
function renderPendingModals(state) {
  // cửa hàng
  if (state.pending_shop_tile) { renderShop(state); }
  else { $("#modal-shop").classList.add("hidden"); }

  // kết thúc ván
  if (state.game_over) {
    const winner = state.winner_id ? findPlayer(state, state.winner_id) : null;
    $("#end-desc").textContent = winner
      ? `${charOf(winner).emoji} ${winner.name} đã chinh phục mê cung thiên thạch và về đích đầu tiên!`
      : "Ván đấu đã kết thúc.";
    $("#modal-end").classList.remove("hidden");
    return;
  } else {
    $("#modal-end").classList.add("hidden");
  }

  const pa = state.pending_action;
  if (!pa) { $("#modal-pending").classList.add("hidden"); return; }

  const actorId = pa.player_id || pa.acting_player_id;
  const isMine = actorId === myPlayerId;

  if (pa.kind === "direction_choice") {
    $("#pending-title").textContent = "🌌 NGÃ BA KHÔNG GIAN";
    if (isMine) {
      $("#pending-desc").textContent = pa.card_desc;
      const opt = $("#pending-options");
      opt.innerHTML = "";
      pa.options.forEach(tileIdx => {
        const tile = state.board.find(t => t.index === tileIdx);
        const btn = document.createElement("button");
        btn.textContent = `${TILE_ICONS[tile.type]} Đi tới ô ${tileIdx} (${TILE_NAMES[tile.type]})`;
        btn.addEventListener("click", () => {
          $("#modal-pending").classList.add("hidden");
          socket.emit("resolve_pending", { room_code: myRoomCode, player_id: myPlayerId, choice: { target: tileIdx } });
        });
        opt.appendChild(btn);
      });
    } else {
      const actor = findPlayer(state, actorId);
      $("#pending-desc").textContent = `Đang chờ ${actor ? actor.name : "người chơi"} chọn hướng đi...`;
      $("#pending-options").innerHTML = "";
    }
    $("#modal-pending").classList.remove("hidden");
    return;
  }

  // Bài Sự Kiện / Bẫy: lật bài trước, sau đó nếu cần chọn (await != null) thì hiện modal chọn
  if (!isMine) {
    $("#pending-title").textContent = pa.kind === "trap" ? "🪤 BÀI BẪY" : "🔮 BÀI SỰ KIỆN";
    const actor = findPlayer(state, actorId);
    $("#pending-desc").textContent = `Đang chờ ${actor ? actor.name : "người chơi"} đưa ra lựa chọn cho "${pa.card_name}"...`;
    $("#pending-options").innerHTML = "";
    if (!cardAnimating) $("#modal-pending").classList.remove("hidden");
    return;
  }

  renderCardChoiceModal(state, pa);
}

function renderCardChoiceModal(state, pa) {
  $("#pending-title").textContent = pa.kind === "trap" ? "🪤 " + pa.card_name : "🔮 " + pa.card_name;
  $("#pending-desc").textContent = pa.card_desc;
  const opt = $("#pending-options");
  opt.innerHTML = "";

  const others = () => state.players.filter(p => p.id !== myPlayerId && !p.finished);

  switch (pa.await) {
    case "single_target": {
      others().forEach(t => addChoiceBtn(opt, `${charOf(t).emoji} ${t.name}`, () => submitChoice({ target_id: t.id })));
      break;
    }
    case "two_targets": {
      pendingSelection.twoTargets = pendingSelection.twoTargets || [];
      state.players.filter(p => !p.finished).forEach(t => {
        const selected = pendingSelection.twoTargets.includes(t.id);
        addChoiceBtn(opt, `${selected ? "✅ " : ""}${charOf(t).emoji} ${t.name}`, () => {
          const arr = pendingSelection.twoTargets;
          const i = arr.indexOf(t.id);
          if (i >= 0) arr.splice(i, 1); else if (arr.length < 2) arr.push(t.id);
          renderCardChoiceModal(state, pa);
        });
      });
      if (pendingSelection.twoTargets.length === 2) {
        addChoiceBtn(opt, "✔ XÁC NHẬN HOÁN ĐỔI", () => {
          submitChoice({ targets: pendingSelection.twoTargets });
          pendingSelection.twoTargets = [];
        });
      }
      break;
    }
    case "copy_choice": {
      pendingSelection.copyTarget = pendingSelection.copyTarget ?? null;
      others().forEach(t => addChoiceBtn(opt, `${pendingSelection.copyTarget === t.id ? "✅ " : ""}${charOf(t).emoji} ${t.name}`, () => {
        pendingSelection.copyTarget = t.id;
        renderCardChoiceModal(state, pa);
      }));
      if (pendingSelection.copyTarget !== null) {
        addChoiceBtn(opt, "Sao chép VỊ TRÍ", () => { submitChoice({ target_id: pendingSelection.copyTarget, field: "position" }); pendingSelection.copyTarget = null; });
        addChoiceBtn(opt, "Sao chép VÀNG", () => { submitChoice({ target_id: pendingSelection.copyTarget, field: "gold" }); pendingSelection.copyTarget = null; });
      }
      break;
    }
    case "tile_choice": {
      addNumberInput(opt, "Số ô (2-99)", (val) => submitChoice({ tile: val }));
      break;
    }
    case "two_tile_choice": {
      addTwoNumberInput(opt, "Ô thứ nhất", "Ô thứ hai", (a, b) => submitChoice({ tile_a: a, tile_b: b }));
      break;
    }
    case "five_tile_choice": {
      addFiveNumberInput(opt, (arr) => submitChoice({ tiles: arr }));
      break;
    }
    case "area_choice": {
      (pa.options || []).forEach(area => addChoiceBtn(opt, `Khu vực ô ${area}`, () => submitChoice({ area })));
      break;
    }
    default:
      addChoiceBtn(opt, "XÁC NHẬN", () => submitChoice({}));
  }
  $("#modal-pending").classList.remove("hidden");

  function submitChoice(choice) {
    $("#modal-pending").classList.add("hidden");
    socket.emit("resolve_pending", { room_code: myRoomCode, player_id: myPlayerId, choice });
  }
}
function addChoiceBtn(container, label, onClick) {
  const btn = document.createElement("button");
  btn.textContent = label;
  btn.addEventListener("click", onClick);
  container.appendChild(btn);
}
function addNumberInput(container, placeholder, onSubmit) {
  const input = document.createElement("input");
  input.type = "number"; input.min = 2; input.max = 99; input.placeholder = placeholder;
  const btn = document.createElement("button");
  btn.textContent = "XÁC NHẬN";
  btn.addEventListener("click", () => { const v = parseInt(input.value, 10); if (v >= 2 && v <= 99) onSubmit(v); });
  container.appendChild(input); container.appendChild(btn);
}
function addTwoNumberInput(container, ph1, ph2, onSubmit) {
  const i1 = document.createElement("input"); i1.type = "number"; i1.min = 2; i1.max = 99; i1.placeholder = ph1;
  const i2 = document.createElement("input"); i2.type = "number"; i2.min = 2; i2.max = 99; i2.placeholder = ph2;
  const btn = document.createElement("button"); btn.textContent = "XÁC NHẬN";
  btn.addEventListener("click", () => {
    const a = parseInt(i1.value, 10), b = parseInt(i2.value, 10);
    if (a >= 2 && a <= 99 && b >= 2 && b <= 99 && a !== b) onSubmit(a, b);
  });
  container.appendChild(i1); container.appendChild(i2); container.appendChild(btn);
}
function addFiveNumberInput(container, onSubmit) {
  const inputs = [];
  for (let i = 0; i < 5; i++) {
    const inp = document.createElement("input");
    inp.type = "number"; inp.min = 2; inp.max = 99; inp.placeholder = `Ô ${i + 1}`;
    inputs.push(inp); container.appendChild(inp);
  }
  const btn = document.createElement("button"); btn.textContent = "XÁC NHẬN";
  btn.addEventListener("click", () => {
    const arr = inputs.map(i => parseInt(i.value, 10));
    if (arr.every(v => v >= 2 && v <= 99) && new Set(arr).size === 5) onSubmit(arr);
  });
  container.appendChild(btn);
}

$("#btn-back-home").addEventListener("click", () => location.reload());

// =====================================================================
// POPUP SỰ KIỆN GIỮA MÀN HÌNH + LẬT BÀI TAROT
// =====================================================================
function flashPopup(icon, text) {
  const popup = $("#event-popup");
  popup.classList.remove("hidden");
  popup.innerHTML = `<div class="event-popup-inner"><div class="event-popup-icon">${icon}</div><div class="event-popup-text">${text}</div></div>`;
  clearTimeout(popup._hideTimer);
  popup._hideTimer = setTimeout(() => popup.classList.add("hidden"), 2500);
}

const EVENT_ICONS = {
  dice_roll: "🎲", branch: "🌌", shop: "🎪", shop_buy: "🛒", gold_gain: "✨", danger: "☄️",
  steal: "🕳️", warp: "🌀", toll: "🚪", trap_reverse: "🪤", shield_block: "🛡️", push_back: "🔫",
  booster: "🚀", skip_turn: "❄️", game_start: "🛰️", game_over: "🏆", use_item: "⚙️",
};

function processNewEvents(state) {
  const feed = state.events_feed || [];
  feed.forEach(ev => {
    if (seenEventIds.has(ev.id)) return;
    seenEventIds.add(ev.id);
    if (ev.kind === "draw_event" || ev.kind === "draw_trap") {
      cardQueue.push(ev);
      processCardQueue();
    } else {
      flashPopup(EVENT_ICONS[ev.kind] || "✨", ev.text);
    }
  });
  // giới hạn bộ nhớ set
  if (seenEventIds.size > 500) {
    seenEventIds = new Set(feed.map(e => e.id));
  }
}

function processCardQueue() {
  if (cardAnimating || cardQueue.length === 0) return;
  cardAnimating = true;
  const ev = cardQueue.shift();
  const isTrap = ev.kind === "draw_trap";
  const modal = $("#modal-card");
  const card = $("#tarot-card");
  const front = $("#tarot-front");

  card.classList.remove("flipped");
  front.classList.toggle("is-trap", isTrap);
  $("#tarot-kind").textContent = isTrap ? "⚠ BÀI BẪY ⚠" : "✦ BÀI SỰ KIỆN ✦";
  $("#tarot-name").textContent = "???";
  $("#tarot-desc").textContent = "";
  modal.classList.remove("hidden");

  setTimeout(() => {
    const card = ev.data && ev.data.card;
    $("#tarot-name").textContent = card ? card.name : (isTrap ? "Bài Bẫy" : "Bài Sự Kiện");
    $("#tarot-desc").textContent = card ? card.desc : "";
    $("#tarot-card").classList.add("flipped");
  }, 700);

  setTimeout(() => {
    modal.classList.add("hidden");
    cardAnimating = false;
    // sau khi lật xong, nếu đang có pending_action cần người này chọn -> hiện modal chọn
    if (latestState) renderPendingModals(latestState);
    processCardQueue();
  }, 2200);
}
