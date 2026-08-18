// 画面全体の状態遷移とユーザー入力を受け持つエントリーポイント。
// API通信はapi.js、実際のDOM描画はrender.jsへ分担している。
import { ApiError, EsperApi } from "./api.js";
import {
  renderGame,
  resetRenderState,
  setConnectionStatus,
} from "./render.js";

const api = new EsperApi();
// currentStateは最後に受け取った公開状態。トグル変更時の再描画に使う。
let currentState = null;
let busy = false;
let toastTimer = null;
// 補助説明はゲーム中に切り替える。初期値は要望どおりOFF。
let assistEnabled = false;
// チャットの流れる通知は初期ON。邪魔な場合はツールバーからOFFにできる。
let chatNotificationsEnabled = true;

// index.html上の固定要素を最初に取得して、以後はID文字列の重複を減らす。
const landingScreen = document.getElementById("landing-screen");
const gameScreen = document.getElementById("game-screen");
const joinForm = document.getElementById("join-form");
const nameInput = document.getElementById("player-name");
const roomInput = document.getElementById("room-id");
const joinRoomButton = document.getElementById("join-room-button");
const inviteBanner = document.getElementById("invite-banner");
const inviteRoomCode = document.getElementById("invite-room-code");
const invitedRoomId = readInvitedRoomId();
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-message");
const toast = document.getElementById("toast");
const rulesDialog = document.getElementById("rules-dialog");
const quickRulesDialog = document.getElementById("quick-rules-dialog");
const entryRulesButton = document.getElementById("entry-rules-button");
const gameRulesButton = document.getElementById("game-rules-button");
const assistToggleButton = document.getElementById("assist-toggle-button");
const assistToggleLabel = document.getElementById("assist-toggle-label");
const chatNoticeToggleButton = document.getElementById("chat-notice-toggle-button");
const chatNoticeToggleLabel = document.getElementById("chat-notice-toggle-label");
const logToggleButton = document.getElementById("log-toggle-button");
const logToggleLabel = document.getElementById("log-toggle-label");
const chatToggleButton = document.getElementById("chat-toggle-button");
const sessionToggleButton = document.getElementById("session-toggle-button");
const logPanel = document.getElementById("log-panel");
const chatPanel = document.getElementById("chat-panel");
const sessionPanel = document.getElementById("session-panel");
const shareRoomButton = document.getElementById("share-room-button");
const utilityPanelBackdrop = document.getElementById("utility-panel-backdrop");
// 横画面では捨て札を画面中央のポップオーバーとして扱うため、向き変更を監視する。
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
// これらの操作が確定した後は、選択に使っていた捨て札パネルを閉じる。
const DISCARD_SELECTION_CONFIRM_ACTIONS = new Set([
  "confirm_healing",
  "confirm_clairvoyance",
  "finish_clairvoyance",
  "select_psychokinesis_push",
]);
// body直下へ一時移動した捨て札パネルを、元のDOM位置へ戻すためのアンカー。
const discardPanelAnchors = Object.fromEntries(
  Object.entries(discardPanels).map(([owner, { panel }]) => [
    owner,
    { parent: panel.parentNode, nextSibling: panel.nextSibling },
  ]),
);

// 横画面のオーバーレイ表示時だけ、捨て札パネルをbody直下へ移す。
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

// 自分/相手どちらかの捨て札パネルを開閉し、横画面では同時に1つだけ表示する。
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

// 選択確定や画面遷移で、開いている捨て札パネルをまとめて閉じる。
function closeDiscardPanels() {
  setDiscardPanelOpen("mine", false);
  setDiscardPanelOpen("opponent", false);
}

// 画面の向きが変わったとき、古い位置/表示状態を残さないようリセットする。
function syncDiscardLayout() {
  closeDiscardPanels();
}

// ログ・チャット・セッション情報のスライドパネルを1つだけ開く。
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

// 古い呼び出し名との互換用。実体は汎用ユーティリティパネル。
function setBattleLogOpen(open) {
  setUtilityPanel(open ? "log" : null);
}

// サイコキネシスなど、操作の続きで相手捨て札を開くためのショートカット。
function openOpponentDiscards() {
  setUtilityPanel();
  setDiscardPanelOpen("opponent", true);
  if (!discardLayoutMedia.matches) {
    window.requestAnimationFrame(() => {
      discardPanels.opponent.panel.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    });
  }
}

// 通信エラーやコピー完了など、短いフィードバックを一定時間だけ表示する。
function showToast(message) {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.classList.add("visible");
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 4200);
}

// API側で整形したエラーはそのまま表示し、それ以外は汎用文にする。
function errorMessage(error) {
  if (error instanceof ApiError) {
    return error.message;
  }
  return "予期しないエラーが発生しました。";
}

// 招待URLのroomパラメータを読み、制御文字や長すぎる値は無視する。
function readInvitedRoomId() {
  const roomId = new URLSearchParams(window.location.search)
    .get("room")
    ?.trim();
  const maxLength = roomInput?.maxLength || 40;
  if (
    !roomId ||
    roomId.length > maxLength ||
    /[\u0000-\u001f\u007f]/.test(roomId)
  ) {
    return null;
  }
  return roomId;
}

// 招待URL由来のあいことばが入力欄と一致しているときだけ、招待表示に切り替える。
function syncInvitePresentation() {
  const isInvitedRoom = Boolean(
    invitedRoomId && roomInput.value.trim() === invitedRoomId,
  );
  inviteBanner.hidden = !isInvitedRoom;
  inviteRoomCode.textContent = isInvitedRoom ? invitedRoomId : "";
  joinRoomButton.textContent = isInvitedRoom
    ? "この部屋に参加する"
    : "入室する";
}

// 初期表示時に招待URLのあいことばを入力欄へ反映する。
function applyRoomInvitation() {
  if (invitedRoomId) {
    roomInput.value = invitedRoomId;
  }
  syncInvitePresentation();
}

// 現在のURLから既存クエリを消し、roomだけを含む共有URLを作る。
function buildRoomInviteUrl(roomId) {
  const url = new URL(window.location.href);
  url.search = "";
  url.hash = "";
  url.searchParams.set("room", roomId);
  return url.toString();
}

// Web Share APIが使えない環境向けに、クリップボードまたはpromptで共有URLを渡す。
async function copyRoomInviteUrl(url) {
  try {
    await navigator.clipboard.writeText(url);
    showToast("招待URLをコピーしました。LINEなどで共有できます。");
  } catch {
    window.prompt("招待URLをコピーしてください。", url);
  }
}

// 補助説明ON/OFFの見た目とアクセシビリティ状態をボタンへ同期する。
function syncAssistToggle() {
  assistToggleButton.setAttribute("aria-pressed", String(assistEnabled));
  assistToggleButton.classList.toggle("active", assistEnabled);
  assistToggleLabel.textContent = assistEnabled ? "補助ON" : "補助OFF";
  assistToggleButton.setAttribute(
    "aria-label",
    assistEnabled ? "補助説明をOFFにする" : "補助説明をONにする",
  );
}

// チャット通知ON/OFFの見た目とアクセシビリティ状態をボタンへ同期する。
function syncChatNoticeToggle() {
  chatNoticeToggleButton.setAttribute(
    "aria-pressed",
    String(chatNotificationsEnabled),
  );
  chatNoticeToggleButton.classList.toggle("active", chatNotificationsEnabled);
  chatNoticeToggleLabel.textContent = chatNotificationsEnabled
    ? "通知ON"
    : "通知OFF";
  chatNoticeToggleButton.setAttribute(
    "aria-label",
    chatNotificationsEnabled
      ? "チャット通知をOFFにする"
      : "チャット通知をONにする",
  );
}

// 入室前/ヘッダーから開く、詳しいルール説明。
function openDetailedRules() {
  rulesDialog.showModal();
}

// 対戦中の邪魔になりにくい簡易ルール説明。
function openQuickRules() {
  quickRulesDialog.showModal();
}

// 入力中のあいことばを招待URL化し、OS共有またはコピーへ流す。
async function shareRoomInvite() {
  const roomId = roomInput.value.trim();
  if (!roomId) {
    showToast("共有するあいことばを入力してください。");
    roomInput.focus();
    return;
  }
  const url = buildRoomInviteUrl(roomId);
  if (typeof navigator.share === "function") {
    try {
      await navigator.share({
        title: "超能力カードゲーム ESPER",
        text: "ESPERの対戦に招待します。リンクを開いて参加してください。",
        url,
      });
      showToast("招待URLを共有しました。");
      return;
    } catch (error) {
      if (error?.name === "AbortError") {
        return;
      }
    }
  }
  await copyRoomInviteUrl(url);
}

// 二重送信を避けるためのロック状態を保存し、aria-busyにも反映する。
function setBusy(value) {
  busy = value;
  document.getElementById("app").setAttribute("aria-busy", String(value));
}

// 対戦画面を閉じて入室画面へ戻し、描画側の一時状態も全てリセットする。
function showLanding() {
  currentState = null;
  document.body.classList.remove("game-active");
  resetRenderState();
  setBattleLogOpen(false);
  syncDiscardLayout();
  gameScreen.hidden = true;
  landingScreen.hidden = false;
  setConnectionStatus(false);
  syncInvitePresentation();
  (inviteBanner.hidden ? roomInput : nameInput).focus();
}

// render.jsへ渡す操作ハンドラ。描画層からAPIや画面遷移の詳細を隠す。
function handlers() {
  return {
    action: performAction,
    openOpponentDiscards,
    rematch: requestRematch,
    leave: leaveRoom,
    returnHome: () => {
      api.clearSession();
      showLanding();
    },
  };
}

// サーバーから受け取った公開状態を保存し、ゲーム画面を再描画する。
function updateState(state, { suppressActionEvents = false } = {}) {
  currentState = state;
  document.body.classList.add("game-active");
  landingScreen.hidden = true;
  gameScreen.hidden = false;
  renderGame(state, handlers(), {
    suppressActionEvents,
    assistEnabled,
    chatNotificationsEnabled,
  });
}

// WebSocketを開き、サーバーからの状態pushをupdateStateへ接続する。
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

// 入室/CPU開始の共通処理。成功したら初期状態表示とWebSocket接続を始める。
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

// ゲーム操作を送信し、戻ってきた状態を即時反映する。
async function performAction(action, payload = {}) {
  if (busy) {
    return;
  }
  setBusy(true);
  try {
    const nextState = await api.performAction(action, payload);
    updateState(nextState);
    // 千里眼で相手捨て札を見た場合は、結果を見逃さないよう相手捨て札を開く。
    const revealsOpponentDiscard =
      action === "confirm_clairvoyance" &&
      nextState.interaction?.kind === "clairvoyance_reveal" &&
      nextState.interaction.options.some(
        (option) => option.selected &&
          option.target?.zone === "opponent_discard",
      );
    if (revealsOpponentDiscard) {
      setDiscardPanelOpen("opponent", true);
    } else if (DISCARD_SELECTION_CONFIRM_ACTIONS.has(action)) {
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

// 終局後の再戦希望を送る。両者が揃うとサーバー側で新しいゲームになる。
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

// 退出時は対人部屋を解散するため、誤操作防止の確認を挟む。
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

// ここから下はDOMイベントの配線。関数本体は上にまとめている。
roomInput.addEventListener("input", syncInvitePresentation);

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

assistToggleButton.addEventListener("click", () => {
  assistEnabled = !assistEnabled;
  syncAssistToggle();
  if (currentState) {
    renderGame(currentState, handlers(), {
      suppressActionEvents: true,
      assistEnabled,
      chatNotificationsEnabled,
    });
  }
});

chatNoticeToggleButton.addEventListener("click", () => {
  chatNotificationsEnabled = !chatNotificationsEnabled;
  syncChatNoticeToggle();
  if (currentState) {
    renderGame(currentState, handlers(), {
      suppressActionEvents: true,
      assistEnabled,
      chatNotificationsEnabled,
    });
  }
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

// Escapeキーは、重なりやすい補助パネル/捨て札パネルを閉じる共通操作にする。
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

shareRoomButton.addEventListener("click", shareRoomInvite);

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

document.getElementById("rules-button").addEventListener("click", openDetailedRules);
entryRulesButton.addEventListener("click", openDetailedRules);
gameRulesButton.addEventListener("click", openQuickRules);

// リロード時にsessionStorageのトークンが生きていれば同じ部屋へ復帰する。
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

// 初期化順序: 招待URL反映、トグル表示同期、レスポンシブ状態同期、セッション復帰。
applyRoomInvitation();
syncAssistToggle();
syncChatNoticeToggle();
syncDiscardLayout();
restoreSession();
