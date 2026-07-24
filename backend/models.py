"""HTTP APIのリクエストモデル。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class JoinRoomRequest(BaseModel):
    room_id: str = Field(min_length=1)
    name: str = "プレイヤー"


class CreateCpuRoomRequest(BaseModel):
    name: str = "プレイヤー"
    level: Literal["easy", "normal", "hard"] = "normal"


class ActionRequest(BaseModel):
    action: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    message: str
