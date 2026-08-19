// ブラウザ側の通信とセッション保存をまとめるモジュール。
// 画面操作はapp.js、DOM描画はrender.jsに任せ、ここではHTTP/WebSocketだけを扱う。
const SESSION_KEY = "esper.session.v1";

export class ApiError extends Error {
  // HTTPステータスを保持して、app.js側で401/404/409などを判定できるようにする。
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class EsperApi {
  constructor() {
    // sessionStorageに残っていれば、リロード後も同じ部屋へ復帰できる。
    this.session = this.loadSession();
    this.socket = null;
    this.socketClosedIntentionally = false;
  }

  loadSession() {
    // 壊れたJSONが残っている場合は、復帰を諦めてセッションを消す。
    try {
      const value = window.sessionStorage.getItem(SESSION_KEY);
      return value ? JSON.parse(value) : null;
    } catch {
      window.sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
  }

  saveSession(data, name) {
    // サーバーのセッション情報に、画面復元用の入力名も一緒に保存する。
    this.session = {
      token: data.token,
      roomId: data.room_id,
      role: data.role,
      name,
    };
    window.sessionStorage.setItem(
      SESSION_KEY,
      JSON.stringify(this.session),
    );
  }

  clearSession() {
    // 部屋から戻るときはWebSocketも閉じ、以後の自動再接続を止める。
    this.disconnect();
    this.session = null;
    window.sessionStorage.removeItem(SESSION_KEY);
  }

  // 以降のメソッドはAPIパスを隠し、app.jsからはゲーム操作名だけで呼べるようにする。
  async joinRoom(roomId, name) {
    const data = await this.request("/api/rooms/join", {
      method: "POST",
      body: { room_id: roomId, name },
      authenticated: false,
    });
    this.saveSession(data, name);
    return data.state;
  }

  async createCpuRoom(level, name) {
    const data = await this.request("/api/rooms/cpu", {
      method: "POST",
      body: { level, name },
      authenticated: false,
    });
    this.saveSession(data, name);
    return data.state;
  }

  getState() {
    return this.roomRequest("state");
  }

  performAction(action, payload = {}) {
    return this.roomRequest("actions", {
      method: "POST",
      body: { action, payload },
    });
  }

  sendChat(message) {
    return this.roomRequest("chat", {
      method: "POST",
      body: { message },
    });
  }

  requestRematch() {
    return this.roomRequest("rematch", { method: "POST" });
  }

  leaveRoom() {
    return this.roomRequest("leave", { method: "POST" });
  }

  roomRequest(endpoint, options = {}) {
    // 部屋IDを毎回呼び出し側へ渡さなくてよいよう、保存済みセッションからURLを組み立てる。
    if (!this.session) {
      throw new ApiError("セッションがありません", 401);
    }
    return this.request(
      `/api/rooms/${encodeURIComponent(this.session.roomId)}/${endpoint}`,
      options,
    );
  }

  async request(
    path,
    {
      method = "GET",
      body,
      authenticated = true,
    } = {},
  ) {
    // JSON送受信、Bearer付与、APIエラー文の取り出しを共通化する。
    const headers = { Accept: "application/json" };
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (authenticated) {
      if (!this.session) {
        throw new ApiError("セッションがありません", 401);
      }
      headers.Authorization = `Bearer ${this.session.token}`;
    }

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        "サーバーへ接続できません。通信状態を確認してください。",
      );
    }

    const contentType = response.headers.get("content-type") || "";
    // エラー応答もJSONならdetailを読み、トーストへ出せる文字列に変換する。
    const data = contentType.includes("application/json")
      ? await response.json()
      : null;
    if (!response.ok) {
      const detail = data?.detail;
      const message = Array.isArray(detail)
        ? detail.map((item) => item.msg).join(" / ")
        : detail || `リクエストに失敗しました (${response.status})`;
      throw new ApiError(message, response.status);
    }
    return data;
  }

  connect({ onState, onStatus, onDisbanded }) {
    // WebSocketは状態同期専用。初回stateでは演出を抑え、差分更新だけ通知する。
    if (!this.session) {
      return;
    }
    this.disconnect();
    this.socketClosedIntentionally = false;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const room = encodeURIComponent(this.session.roomId);
    const token = encodeURIComponent(this.session.token);
    const socket = new WebSocket(
      `${protocol}//${window.location.host}/ws/rooms/${room}?token=${token}`,
    );
    this.socket = socket;
    let awaitingInitialState = true;

    socket.addEventListener("open", () => onStatus(true));
    socket.addEventListener("message", (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type !== "state") {
        return;
      }
      onState(message.data, {
        suppressActionEvents: awaitingInitialState,
      });
      awaitingInitialState = false;
      if (message.data.game.turn_step === "ROOM_DISBANDED") {
        this.socketClosedIntentionally = true;
        onDisbanded();
      }
    });
    socket.addEventListener("close", () => {
      onStatus(false);
      // 意図しない切断なら少し待って自動再接続する。
      if (!this.socketClosedIntentionally && this.session) {
        window.setTimeout(
          () => this.connect({ onState, onStatus, onDisbanded }),
          1500,
        );
      }
    });
    socket.addEventListener("error", () => onStatus(false));
  }

  disconnect() {
    // 手動で閉じた接続は、closeイベント後の自動再接続を走らせない。
    this.socketClosedIntentionally = true;
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
