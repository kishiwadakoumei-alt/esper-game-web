"""対戦部屋への入室、CPU戦作成、再戦、退出を管理するサービス。

rooms辞書に対して部屋を作る/消す責務だけを持ち、HTTPや描画は扱わない。
"""

import time
from dataclasses import dataclass

from game_logic import EsperGame


@dataclass(frozen=True)
class JoinResult:
    """対戦部屋への入室結果。

    errorが入っている場合は入室失敗、roleが入っている場合はp1/p2割り当て成功。
    """

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
        """あいことばの部屋へ、空き状況に応じてp1/p2として参加させる。"""
        if room_id not in rooms:
            rooms[room_id] = EsperGame()

        game = rooms[room_id]
        if len(game.players) == 0:
            game.players.append(player_name)
            return JoinResult(game=game, role="p1")

        if len(game.players) == 1:
            # 2人目が入った時点で対戦準備完了。先攻抽選はAPI側のタスクで行う。
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
        """CPUをp2として入れた専用部屋を作成する。"""
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
        """CPU戦ではCPU側の再戦承認を自動で入れる。"""
        if game.is_cpu:
            game.rematch_requests.add("p2")

    @staticmethod
    def request_rematch(game: EsperGame, role: str) -> bool:
        """再戦希望を記録し、両者が揃ったらゲームをリセットしてTrueを返す。"""
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
        """退出時に部屋を解散状態へ変え、rooms辞書から取り除く。"""
        game.turn_step = "ROOM_DISBANDED"
        if room_id in rooms:
            del rooms[room_id]
