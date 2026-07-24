"""APIクライアントのルーム・役割を安全に解決するセッション管理。"""

import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerSession:
    token: str
    room_id: str
    role: str
    player_name: str


class SessionStore:
    """プロセス内でランダムなセッショントークンを管理する。"""

    def __init__(self) -> None:
        self._sessions: dict[str, PlayerSession] = {}

    def create(
        self,
        room_id: str,
        role: str,
        player_name: str,
    ) -> PlayerSession:
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
        return self._sessions.get(token)

    def remove_room(self, room_id: str) -> None:
        tokens = [
            token
            for token, session in self._sessions.items()
            if session.room_id == room_id
        ]
        for token in tokens:
            self._sessions.pop(token, None)
