"""ルーム別WebSocket接続とプレイヤー別状態配信を管理する。

同じ部屋でもプレイヤーごとに見える情報が違うため、配信直前に
各セッションのroleを使ってStateServiceで公開状態を作り直す。
"""

from collections import defaultdict

from fastapi import WebSocket

from game_logic import EsperGame
from services import StateService

from .session_store import PlayerSession, SessionStore


class ConnectionManager:
    """同じセッションの複数タブを含むWebSocket接続を保持する。

    構造は room_id -> session_token -> WebSocket集合。
    1人が複数タブを開いても、それぞれへ同じ視点の状態を配信できる。
    """

    def __init__(self) -> None:
        self._connections: dict[
            str,
            dict[str, set[WebSocket]],
        ] = defaultdict(lambda: defaultdict(set))

    async def connect(
        self,
        websocket: WebSocket,
        session: PlayerSession,
        game: EsperGame,
    ) -> None:
        """WebSocketを受け入れ、接続直後に現在状態を1回送る。"""
        await websocket.accept()
        self._connections[session.room_id][session.token].add(websocket)
        await self.send_state(websocket, session, game)

    def disconnect(
        self,
        websocket: WebSocket,
        session: PlayerSession,
    ) -> None:
        """切断したWebSocketだけを集合から除き、空になった階層を片付ける。"""
        room_connections = self._connections.get(session.room_id)
        if not room_connections:
            return
        token_connections = room_connections.get(session.token)
        if token_connections:
            token_connections.discard(websocket)
            if not token_connections:
                room_connections.pop(session.token, None)
        if not room_connections:
            self._connections.pop(session.room_id, None)

    async def send_state(
        self,
        websocket: WebSocket,
        session: PlayerSession,
        game: EsperGame,
    ) -> None:
        """単一WebSocketへ、そのセッション視点の状態を送る。"""
        await websocket.send_json({
            "type": "state",
            "data": StateService.build_public_state(
                game,
                session.role,
                room_id=session.room_id,
            ),
        })

    async def broadcast(
        self,
        room_id: str,
        game: EsperGame,
        sessions: SessionStore,
    ) -> None:
        """部屋内の全接続へ、それぞれのプレイヤー視点で状態を配信する。"""
        room_connections = self._connections.get(room_id, {})
        deliveries: list[tuple[WebSocket, dict]] = []

        for token, sockets in list(room_connections.items()):
            session = sessions.get(token)
            if session is None or session.room_id != room_id:
                continue
            # payloadはセッションごとに作る。p1とp2では秘匿情報の見え方が違う。
            payload = {
                "type": "state",
                "data": StateService.build_public_state(
                    game,
                    session.role,
                    room_id=room_id,
                ),
            }
            deliveries.extend(
                (websocket, payload) for websocket in list(sockets)
            )

        for websocket, payload in deliveries:
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                # 切断イベント側でも除去するため、送信失敗は無視する。
                pass

    async def close_room(self, room_id: str) -> None:
        """部屋解散時に、残っているWebSocketを正常終了コードで閉じる。"""
        room_connections = self._connections.pop(room_id, {})
        for sockets in room_connections.values():
            for websocket in list(sockets):
                try:
                    await websocket.close(code=1000)
                except RuntimeError:
                    pass
