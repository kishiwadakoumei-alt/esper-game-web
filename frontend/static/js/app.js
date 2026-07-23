import { ApiError, EsperApi } from "./api.js";
import {
  renderGame,
  resetRenderState,
  setConnectionStatus,
} from "./render.js";

const api = new EsperApi();
let currentState = null;
let busy = false;
let toastTimer = null;

const landingScreen = document.getElementById("landing-screen");
const gameScreen = document.getElementById("game-screen");
const joinForm = document.getElementById("join-form");
const nameInput = document.getElementById("player-name");
const roomInput = document.getElementById("room-id");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-message");
const toast = document.getElementById("toast");
const rulesDialog = document.getElementById("rules-dialog");

function showToast(message) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("visible");
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 4200);
}

function errorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "予期しないエラーが発生しました。";
}

function setBusy(value) {
  busy = value;
  document.getElementById("app").setAttribute("aria-busy", String(value));
}

function showLanding() {
  currentState = null;
  resetRenderState();
  gameScreen.hidden = true;
  landingScreen.hidden = false;
  setConnectionStatus(false);
  roomInput.focus();
}

function handlers() {
  return {
    action: performAction,
    rematch: requestRematch,
    leave: leaveRoom,
    returnHome: () => {
      api.clearSession();
      showLanding();
    },
  };
}

function updateState(state, { suppressActionEvents = false } = {}) {
  currentState = state;
  landingScreen.hidden = true;
  gameScreen.hidden = false;
  renderGame(state, handlers(), { suppressActionEvents });
}

function connectSocket() {
  api.connect({
    onState: updateState,
    onStatus: setConnectionStatus,
    onDisbanded: () => {
      api.clearSession();
      showToast("対戦相手が退出し、ルームが解散されました。");
    },
  });
}

async function enterGame(operation) {
  if (busy) {
    return;
  }
  setBusy(true);
  try {
    const state = await operation();
    updateState(state);
    connectSocket();
  } catch (error) {
    showToast(errorMessage(error));
  } finally {
    setBusy(false);
  }
}

async function performAction(action, payload = {}) {
  if (busy) {
    return;
  }
  setBusy(true);
  try {
    updateState(await api.performAction(action, payload));
  } catch (error) {
    showToast(errorMessage(error));
    if (error instanceof ApiError && error.status === 409) {
      try {
        updateState(await api.getState());
      } catch {
        // WebSocketによる次の状態更新に任せる。
      }
    }
  } finally {
    setBusy(false);
  }
}

async function requestRematch() {
  if (busy) {
    return;
  }
  setBusy(true);
  try {
    updateState(await api.requestRematch());
  } catch (error) {
    showToast(errorMessage(error));
  } finally {
    setBusy(false);
  }
}

async function leaveRoom() {
  if (busy || !api.session) {
    return;
  }
  if (!window.confirm("ルームを退出しますか？ 対人戦では部屋が解散されます。")) {
    return;
  }
  setBusy(true);
  try {
    await api.leaveRoom();
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 404)) {
      showToast(errorMessage(error));
    }
  } finally {
    api.clearSession();
    showLanding();
    setBusy(false);
  }
}

joinForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const name = nameInput.value.trim() || "プレイヤー";
  const roomId = roomInput.value.trim();
  if (!roomId) {
    showToast("あいことばを入力してください。");
    roomInput.focus();
    return;
  }
  enterGame(() => api.joinRoom(roomId, name));
});

document.querySelectorAll("[data-cpu-level]").forEach((button) => {
  button.addEventListener("click", () => {
    const name = nameInput.value.trim() || "プレイヤー";
    enterGame(() => api.createCpuRoom(button.dataset.cpuLevel, name));
  });
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message || busy) {
    return;
  }
  setBusy(true);
  try {
    updateState(await api.sendChat(message));
    chatInput.value = "";
  } catch (error) {
    showToast(errorMessage(error));
  } finally {
    setBusy(false);
  }
});

document.getElementById("leave-button").addEventListener("click", leaveRoom);

document.getElementById("copy-room-button").addEventListener("click", async () => {
  if (!api.session) {
    return;
  }
  try {
    await navigator.clipboard.writeText(api.session.roomId);
    showToast("あいことばをコピーしました。");
  } catch {
    showToast(`あいことば: ${api.session.roomId}`);
  }
});

document.getElementById("rules-button").addEventListener("click", () => {
  rulesDialog.showModal();
});

async function restoreSession() {
  if (!api.session) {
    showLanding();
    return;
  }
  nameInput.value = api.session.name || "プレイヤー";
  try {
    updateState(await api.getState());
    connectSocket();
  } catch (error) {
    api.clearSession();
    showLanding();
    if (!(error instanceof ApiError && [401, 404].includes(error.status))) {
      showToast(errorMessage(error));
    }
  }
}

restoreSession();
