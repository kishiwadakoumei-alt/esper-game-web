"""対戦部屋への入室、CPU戦作成、再戦、退出を管理するサービス。"""

import time
from dataclasses import dataclass

from game_logic import EsperGame


@dataclass(frozen=True)
class JoinResult:
    """対戦部屋への入室結果。"""

    game: EsperGame | None
    role: str | None
    error: str | None = None


class RoomService:
    """プロセス内の対戦部屋に対する操作を提供する。"""

    @staticmethod
    def join_room(
        rooms: dict[str, EsperGame],
        room_id: str,
        player_name: str,
    ) -> JoinResult:
        if room_id not in rooms:
            rooms[room_id] = EsperGame()

        game = rooms[room_id]
        if len(game.players) == 0:
            game.players.append(player_name)
            return JoinResult(game=game, role="p1")

        if len(game.players) == 1:
            game.players.append(player_name)
            game.turn_step = "DECIDING_TURN"
            game.timer_started = False
            return JoinResult(game=game, role="p2")

        return JoinResult(
            game=None,
            role=None,
            error="その部屋はすでに満員です！",
        )

    @staticmethod
    def create_cpu_room(
        rooms: dict[str, EsperGame],
        player_name: str,
        level: str,
        name_suffix: str,
        *,
        room_id: str | None = None,
    ) -> tuple[str, EsperGame]:
        cpu_room_id = room_id or f"cpu_room_{int(time.time())}"
        game = EsperGame()
        game.is_cpu = True
        game.cpu_level = level
        game.players.append(player_name)
        game.players.append(f"CPU（{name_suffix}）")
        game.turn_step = "DECIDING_TURN"
        game.timer_started = False
        rooms[cpu_room_id] = game
        return cpu_room_id, game

    @staticmethod
    def accept_cpu_rematch(game: EsperGame) -> None:
        if game.is_cpu:
            game.rematch_requests.add("p2")

    @staticmethod
    def request_rematch(game: EsperGame, role: str) -> bool:
        game.rematch_requests.add(role)
        if len(game.rematch_requests) == 2:
            game.reset_game()
            return True
        return False

    @staticmethod
    def disband_room(
        rooms: dict[str, EsperGame],
        room_id: str,
        game: EsperGame,
    ) -> None:
        game.turn_step = "ROOM_DISBANDED"
        if room_id in rooms:
            del rooms[room_id]
