"""FastAPIプロセス内のルーム、接続、非同期タスクを管理する。

永続DBを使わない構成なので、部屋・セッション・WebSocket接続・CPU処理は
このプロセス内のApplicationContextへまとめて保持する。
"""

import asyncio

from game_logic import EsperGame
from services import CpuService, GameService, RoomService

from .connection_manager import ConnectionManager
from .session_store import SessionStore


class ApplicationContext:
    """単一プロセス用のバックエンド共有状態。

    テスト時はroulette_delay/cpu_delayを短くできるよう、遅延時間を注入可能にしている。
    """

    def __init__(
        self,
        *,
        roulette_delay: float = 1.5,
        cpu_delay: float = 1.0,
    ) -> None:
        # roomsがゲーム本体、sessionsがブラウザごとの認証、connectionsが配信先を持つ。
        self.rooms: dict[str, EsperGame] = {}
        self.sessions = SessionStore()
        self.connections = ConnectionManager()
        self.roulette_delay = roulette_delay
        self.cpu_delay = cpu_delay
        # 部屋単位のロックで、同じゲームへ複数HTTPリクエストが同時に触るのを防ぐ。
        self._locks: dict[str, asyncio.Lock] = {}
        self._roulette_tasks: dict[str, asyncio.Task] = {}
        self._cpu_tasks: dict[str, asyncio.Task] = {}

    def room_lock(self, room_id: str) -> asyncio.Lock:
        """部屋IDごとに同じasyncio.Lockを再利用する。"""
        if room_id not in self._locks:
            self._locks[room_id] = asyncio.Lock()
        return self._locks[room_id]

    async def broadcast(self, room_id: str, game: EsperGame) -> None:
        """接続中の全クライアントへ、各自視点の公開状態を送る。"""
        await self.connections.broadcast(
            room_id,
            game,
            self.sessions,
        )

    def schedule_roulette(self, room_id: str) -> None:
        """先攻抽選タスクを、同じ部屋で二重起動しないよう予約する。"""
        existing = self._roulette_tasks.get(room_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run_roulette(room_id))
        self._roulette_tasks[room_id] = task
        task.add_done_callback(
            lambda completed: self._remove_completed_task(
                self._roulette_tasks,
                room_id,
                completed,
            )
        )

    async def _run_roulette(self, room_id: str) -> None:
        """待機演出後に先攻を決め、必要ならCPUの初手も予約する。"""
        await asyncio.sleep(self.roulette_delay)
        lock = self.room_lock(room_id)
        async with lock:
            game = self.rooms.get(room_id)
            # 途中で退出・再戦などにより状態が変わっていたら抽選を中止する。
            if game is None or game.turn_step != "DECIDING_TURN":
                return
            GameService.decide_first_player(game)

        await self.broadcast(room_id, game)
        self.schedule_cpu(room_id)

    def schedule_cpu(self, room_id: str) -> None:
        """CPUが行動可能な状態なら、1部屋1つだけCPUタスクを予約する。"""
        game = self.rooms.get(room_id)
        if game is None or not CpuService.can_act(game):
            return
        existing = self._cpu_tasks.get(room_id)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._run_cpu(room_id))
        self._cpu_tasks[room_id] = task
        task.add_done_callback(
            lambda completed: self._remove_completed_task(
                self._cpu_tasks,
                room_id,
                completed,
            )
        )

    async def _run_cpu(self, room_id: str) -> None:
        """CPUが行動可能な間、遅延を挟みながら1ステップずつ進める。"""
        game: EsperGame | None = None
        try:
            while True:
                lock = self.room_lock(room_id)
                async with lock:
                    game = self.rooms.get(room_id)
                    # begin_actionでcpu_actingを立て、同時タスクが同じCPUを動かさないようにする。
                    if game is None or not CpuService.begin_action(game):
                        return

                await asyncio.sleep(self.cpu_delay)

                async with lock:
                    game = self.rooms.get(room_id)
                    if game is None:
                        return
                    try:
                        CpuService.take_step(game)
                        RoomService.accept_cpu_rematch(game)
                    finally:
                        CpuService.finish_action(game)

                await self.broadcast(room_id, game)
        finally:
            if game is not None and game.cpu_acting:
                CpuService.finish_action(game)

    def cancel_room_tasks(self, room_id: str) -> None:
        """退出時に、その部屋に紐づく抽選/CPUタスクとロックを破棄する。"""
        for tasks in (self._roulette_tasks, self._cpu_tasks):
            task = tasks.pop(room_id, None)
            if task is not None and not task.done():
                task.cancel()
        self._locks.pop(room_id, None)

    async def shutdown(self) -> None:
        """アプリ終了時に残っているバックグラウンドタスクを全てキャンセルする。"""
        tasks = [
            task
            for task in (
                list(self._roulette_tasks.values())
                + list(self._cpu_tasks.values())
            )
            if not task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._roulette_tasks.clear()
        self._cpu_tasks.clear()

    @staticmethod
    def _remove_completed_task(
        tasks: dict[str, asyncio.Task],
        room_id: str,
        completed: asyncio.Task,
    ) -> None:
        """完了済みタスクだけを辞書から外し、例外があればイベントループへ通知する。"""
        if tasks.get(room_id) is completed:
            tasks.pop(room_id, None)
        if not completed.cancelled():
            completed.exception()
