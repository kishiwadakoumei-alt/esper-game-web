"""APIクライアントのルーム・役割を安全に解決するセッション管理。

ブラウザにはランダムトークンだけを渡し、サーバー側で部屋ID・役割・表示名を引く。
"""

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerSession:
    """1つのブラウザセッションが、どの部屋のどちらの役割かを表す。"""

    token: str
    room_id: str
    role: str
    player_name: str


class SessionStore:
    """プロセス内でランダムなセッショントークンを管理する。

    永続化はしていないため、サーバープロセス再起動時は再入室が必要になる。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, PlayerSession] = {}

    def create(
        self,
        room_id: str,
        role: str,
        player_name: str,
    ) -> PlayerSession:
        """推測困難なトークンを発行し、以後のAPI認証に使う。"""
        token = secrets.token_urlsafe(32)
        session = PlayerSession(
            token=token,
            room_id=room_id,
            role=role,
            player_name=player_name,
        )
        self._sessions[token] = session
        return session

    def get(self, token: str) -> PlayerSession | None:
        """トークンからセッション情報を取得する。存在しなければNone。"""
        return self._sessions.get(token)

    def remove_room(self, room_id: str) -> None:
        """部屋解散時に、その部屋へ属する全セッションを削除する。"""
        tokens = [
            token
            for token, session in self._sessions.items()
            if session.room_id == room_id
        ]
        for token in tokens:
            self._sessions.pop(token, None)
