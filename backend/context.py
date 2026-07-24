"""FastAPIプロセス内のルーム、接続、非同期タスクを管理する。"""

import asyncio

from game_logic import EsperGame
from services import CpuService, GameService, RoomService

from .connection_manager import ConnectionManager
from .session_store import SessionStore


class ApplicationContext:
    """単一プロセス用のバックエンド共有状態。"""

    def __init__(
        self,
        *,
        roulette_delay: float = 1.5,
        cpu_delay: float = 1.0,
    ) -> None:
        self.rooms: dict[str, EsperGame] = {}
        self.sessions = SessionStore()
        self.connections = ConnectionManager()
        self.roulette_delay = roulette_delay
        self.cpu_delay = cpu_delay
        self._locks: dict[str, asyncio.Lock] = {}
        self._roulette_tasks: dict[str, asyncio.Task] = {}
        self._cpu_tasks: dict[str, asyncio.Task] = {}

    def room_lock(self, room_id: str) -> asyncio.Lock:
        if room_id not in self._locks:
            self._locks[room_id] = asyncio.Lock()
        return self._locks[room_id]

    async def broadcast(self, room_id: str, game: EsperGame) -> None:
        await self.connections.broadcast(
            room_id,
            game,
            self.sessions,
        )

    def schedule_roulette(self, room_id: str) -> None:
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
        await asyncio.sleep(self.roulette_delay)
        lock = self.room_lock(room_id)
        async with lock:
            game = self.rooms.get(room_id)
            if game is None or game.turn_step != "DECIDING_TURN":
                return
            GameService.decide_first_player(game)

        await self.broadcast(room_id, game)
        self.schedule_cpu(room_id)

    def schedule_cpu(self, room_id: str) -> None:
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
        game: EsperGame | None = None
        try:
            while True:
                lock = self.room_lock(room_id)
                async with lock:
                    game = self.rooms.get(room_id)
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
        for tasks in (self._roulette_tasks, self._cpu_tasks):
            task = tasks.pop(room_id, None)
            if task is not None and not task.done():
                task.cancel()
        self._locks.pop(room_id, None)

    async def shutdown(self) -> None:
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
        if tasks.get(room_id) is completed:
            tasks.pop(room_id, None)
        if not completed.cancelled():
            completed.exception()
