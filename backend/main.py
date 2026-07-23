"""ESPERのHTTP APIとWebSocketを提供するFastAPIアプリ。"""

from contextlib import asynccontextmanager
import secrets
from typing import Annotated

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from services import GameService, RoomService, StateService

from .command_service import CommandService
from .context import ApplicationContext
from .models import (
    ActionRequest,
    ChatRequest,
    CreateCpuRoomRequest,
    JoinRoomRequest,
)
from .session_store import PlayerSession


def create_app(
    *,
    roulette_delay: float = 1.5,
    cpu_delay: float = 1.0,
) -> FastAPI:
    context = ApplicationContext(
        roulette_delay=roulette_delay,
        cpu_delay=cpu_delay,
    )

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        yield
        await context.shutdown()

    application = FastAPI(
        title="ESPER Game API",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.context = context

    @application.get("/")
    async def root() -> dict:
        return {
            "name": "ESPER Game API",
            "status": "ok",
        }

    @application.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @application.post("/api/rooms/join")
    async def join_room(body: JoinRoomRequest) -> dict:
        room_id = body.room_id
        async with context.room_lock(room_id):
            result = RoomService.join_room(
                context.rooms,
                room_id,
                body.name,
            )
            if result.error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=result.error,
                )
            session = context.sessions.create(
                room_id,
                result.role,
                body.name,
            )
            game = result.game
            response = _session_response(session, game)

        await context.broadcast(room_id, game)
        if game.turn_step == "DECIDING_TURN":
            context.schedule_roulette(room_id)
        return response

    @application.post("/api/rooms/cpu")
    async def create_cpu_room(body: CreateCpuRoomRequest) -> dict:
        suffixes = {
            "easy": "初級",
            "normal": "中級",
            "hard": "上級",
        }
        room_id, game = RoomService.create_cpu_room(
            context.rooms,
            body.name,
            body.level,
            suffixes[body.level],
            room_id=f"cpu_room_{secrets.token_urlsafe(8)}",
        )
        session = context.sessions.create(
            room_id,
            "p1",
            body.name,
        )
        context.schedule_roulette(room_id)
        return _session_response(session, game)

    @application.get("/api/rooms/{room_id}/state")
    async def get_state(
        room_id: str,
        token: Annotated[str, Depends(_bearer_token)],
    ) -> dict:
        session, game = _session_and_game(context, token, room_id)
        return StateService.build_public_state(
            game,
            session.role,
            room_id=room_id,
        )

    @application.post("/api/rooms/{room_id}/actions")
    async def perform_action(
        room_id: str,
        body: ActionRequest,
        token: Annotated[str, Depends(_bearer_token)],
    ) -> dict:
        session = _session_for_room(context, token, room_id)
        async with context.room_lock(room_id):
            game = _game_or_404(context, room_id)
            CommandService.execute(
                game,
                session,
                body.action,
                body.payload,
            )
            RoomService.accept_cpu_rematch(game)
            state_data = StateService.build_public_state(
                game,
                session.role,
                room_id=room_id,
            )

        await context.broadcast(room_id, game)
        context.schedule_cpu(room_id)
        return state_data

    @application.post("/api/rooms/{room_id}/chat")
    async def send_chat(
        room_id: str,
        body: ChatRequest,
        token: Annotated[str, Depends(_bearer_token)],
    ) -> dict:
        session = _session_for_room(context, token, room_id)
        async with context.room_lock(room_id):
            game = _game_or_404(context, room_id)
            if not GameService.send_chat(
                game,
                session.player_name,
                body.message,
            ):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="空のメッセージは送信できません",
                )
            state_data = StateService.build_public_state(
                game,
                session.role,
                room_id=room_id,
            )

        await context.broadcast(room_id, game)
        return state_data

    @application.post("/api/rooms/{room_id}/rematch")
    async def request_rematch(
        room_id: str,
        token: Annotated[str, Depends(_bearer_token)],
    ) -> dict:
        session = _session_for_room(context, token, room_id)
        async with context.room_lock(room_id):
            game = _game_or_404(context, room_id)
            public_state = StateService.build_public_state(
                game,
                session.role,
                room_id=room_id,
            )
            if "request_rematch" not in public_state["available_actions"]:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="現在は再戦を要求できません",
                )
            reset = RoomService.request_rematch(game, session.role)
            state_data = StateService.build_public_state(
                game,
                session.role,
                room_id=room_id,
            )

        await context.broadcast(room_id, game)
        if reset:
            context.schedule_roulette(room_id)
        return state_data

    @application.post("/api/rooms/{room_id}/leave")
    async def leave_room(
        room_id: str,
        token: Annotated[str, Depends(_bearer_token)],
    ) -> dict:
        _session_for_room(context, token, room_id)
        async with context.room_lock(room_id):
            game = _game_or_404(context, room_id)
            RoomService.disband_room(context.rooms, room_id, game)

        await context.broadcast(room_id, game)
        await context.connections.close_room(room_id)
        context.sessions.remove_room(room_id)
        context.cancel_room_tasks(room_id)
        return {"status": "disbanded"}

    @application.websocket("/ws/rooms/{room_id}")
    async def room_websocket(
        websocket: WebSocket,
        room_id: str,
        token: Annotated[str, Query(min_length=1)],
    ) -> None:
        session = context.sessions.get(token)
        game = context.rooms.get(room_id)
        if (
            session is None
            or session.room_id != room_id
            or game is None
        ):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        await context.connections.connect(websocket, session, game)
        try:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
        except WebSocketDisconnect:
            pass
        finally:
            context.connections.disconnect(websocket, session)

    return application


def _bearer_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearerトークンが必要です",
        )
    token = authorization[len(prefix):].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearerトークンが必要です",
        )
    return token


def _session_for_room(
    context: ApplicationContext,
    token: str,
    room_id: str,
) -> PlayerSession:
    session = context.sessions.get(token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なセッションです",
        )
    if session.room_id != room_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="別のルームのセッションです",
        )
    return session


def _game_or_404(
    context: ApplicationContext,
    room_id: str,
):
    game = context.rooms.get(room_id)
    if game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ルームが見つかりません",
        )
    return game


def _session_and_game(
    context: ApplicationContext,
    token: str,
    room_id: str,
):
    session = _session_for_room(context, token, room_id)
    return session, _game_or_404(context, room_id)


def _session_response(session: PlayerSession, game) -> dict:
    return {
        "token": session.token,
        "room_id": session.room_id,
        "role": session.role,
        "state": StateService.build_public_state(
            game,
            session.role,
            room_id=session.room_id,
        ),
    }


app = create_app()
