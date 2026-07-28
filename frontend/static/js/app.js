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
const logToggleButton = document.getElementById("log-toggle-button");
const logToggleLabel = document.getElementById("log-toggle-label");
const chatToggleButton = document.getElementById("chat-toggle-button");
const sessionToggleButton = document.getElementById("session-toggle-button");
const logPanel = document.getElementById("log-panel");
const chatPanel = document.getElementById("chat-panel");
const sessionPanel = document.getElementById("session-panel");
const utilityPanelBackdrop = document.getElementById("utility-panel-backdrop");
const discardLayoutMedia = window.matchMedia("(orientation: landscape)");
const discardPanels = {
  mine: {
    button: document.getElementById("my-discard-toggle-button"),
    panel: document.getElementById("my-discard-panel"),
  },
  opponent: {
    button: document.getElementById("opponent-discard-toggle-button"),
    panel: document.getElementById("opponent-discard-panel"),
  },
};
const DISCARD_SELECTION_CONFIRM_ACTIONS = new Set([
  "confirm_healing",
  "confirm_clairvoyance",
  "select_psychokinesis_push",
]);
const discardPanelAnchors = Object.fromEntries(
  Object.entries(discardPanels).map(([owner, { panel }]) => [
    owner,
    { parent: panel.parentNode, nextSibling: panel.nextSibling },
  ]),
);

function placeDiscardPanel(owner, inViewportLayer) {
  const panel = discardPanels[owner].panel;
  if (inViewportLayer) {
    document.body.append(panel);
    return;
  }
  const { parent, nextSibling } = discardPanelAnchors[owner];
  if (panel.parentNode !== parent) {
    parent.insertBefore(panel, nextSibling);
  }
}

function setDiscardPanelOpen(owner, open) {
  const landscape = discardLayoutMedia.matches;
  if (open && landscape) {
    Object.entries(discardPanels).forEach(([otherOwner, entry]) => {
      if (otherOwner === owner) {
        return;
      }
      entry.panel.hidden = true;
      entry.button.setAttribute("aria-expanded", "false");
      entry.button.classList.remove("open");
      entry.panel.setAttribute("aria-modal", "false");
      placeDiscardPanel(otherOwner, false);
    });
  }
  const { button, panel } = discardPanels[owner];
  const visible = !landscape || open;
  panel.hidden = !visible;
  panel.setAttribute("aria-modal", String(landscape && visible));
  placeDiscardPanel(owner, landscape && visible);
  button.setAttribute("aria-expanded", String(visible));
  button.classList.toggle("open", visible && landscape);
  document.body.classList.toggle(
    "discard-panel-open",
    landscape &&
      Object.values(discardPanels).some((entry) => !entry.panel.hidden),
  );
}

function closeDiscardPanels() {
  setDiscardPanelOpen("mine", false);
  setDiscardPanelOpen("opponent", false);
}

function syncDiscardLayout() {
  closeDiscardPanels();
}

function setUtilityPanel(openPanel = null) {
  const logOpen = openPanel === "log";
  const chatOpen = openPanel === "chat";
  const sessionOpen = openPanel === "session";
  logPanel.hidden = !logOpen;
  chatPanel.hidden = !chatOpen;
  sessionPanel.hidden = !sessionOpen;
  utilityPanelBackdrop.hidden = !logOpen && !chatOpen && !sessionOpen;
  logToggleButton.setAttribute("aria-expanded", String(logOpen));
  chatToggleButton.setAttribute("aria-expanded", String(chatOpen));
  sessionToggleButton.setAttribute("aria-expanded", String(sessionOpen));
  logToggleButton.classList.toggle("open", logOpen);
  chatToggleButton.classList.toggle("open", chatOpen);
  sessionToggleButton.classList.toggle("open", sessionOpen);
  logToggleLabel.textContent = "バトルログ";
  document.body.classList.toggle(
    "utility-panel-open",
    logOpen || chatOpen || sessionOpen,
  );
  if (chatOpen) {
    chatInput.focus();
  }
}

function setBattleLogOpen(open) {
  setUtilityPanel(open ? "log" : null);
}

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
  document.body.classList.remove("game-active");
  resetRenderState();
  setBattleLogOpen(false);
  syncDiscardLayout();
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
  document.body.classList.add("game-active");
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
    if (DISCARD_SELECTION_CONFIRM_ACTIONS.has(action)) {
      closeDiscardPanels();
    }
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

logToggleButton.addEventListener("click", () => {
  setUtilityPanel(logPanel.hidden ? "log" : null);
});

chatToggleButton.addEventListener("click", () => {
  setUtilityPanel(chatPanel.hidden ? "chat" : null);
});

sessionToggleButton.addEventListener("click", () => {
  setUtilityPanel(sessionPanel.hidden ? "session" : null);
});

document.getElementById("session-close-button").addEventListener(
  "click",
  () => setUtilityPanel(),
);

document.getElementById("log-close-button").addEventListener("click", () => {
  setUtilityPanel();
});

document.getElementById("chat-close-button").addEventListener("click", () => {
  setUtilityPanel();
});

utilityPanelBackdrop.addEventListener("click", () => {
  setUtilityPanel();
});

Object.entries(discardPanels).forEach(([owner, { button, panel }]) => {
  button.addEventListener("click", () => {
    setDiscardPanelOpen(owner, panel.hidden);
  });
});

document.getElementById("my-discard-close-button").addEventListener(
  "click",
  () => setDiscardPanelOpen("mine", false),
);

document.getElementById("opponent-discard-close-button").addEventListener(
  "click",
  () => setDiscardPanelOpen("opponent", false),
);

discardLayoutMedia.addEventListener("change", syncDiscardLayout);

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }
  if (!logPanel.hidden || !chatPanel.hidden || !sessionPanel.hidden) {
    setUtilityPanel();
  } else if (!discardPanels.mine.panel.hidden) {
    setDiscardPanelOpen("mine", false);
  } else if (!discardPanels.opponent.panel.hidden) {
    setDiscardPanelOpen("opponent", false);
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

syncDiscardLayout();
restoreSession();
