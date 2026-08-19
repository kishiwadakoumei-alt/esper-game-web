"""HTTP APIのリクエストモデル。

FastAPI/Pydanticで受け取るJSONの形を定義する。
細かいゲーム上の検証はCommandService側で公開状態と照合する。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class JoinRoomRequest(BaseModel):
    """対人部屋へ入室するときの名前とあいことば。"""
    room_id: str = Field(min_length=1)
    name: str = "プレイヤー"


class CreateCpuRoomRequest(BaseModel):
    """CPU戦を始めるときの名前と難易度。"""
    name: str = "プレイヤー"
    level: Literal["easy", "normal", "hard"] = "normal"


class ActionRequest(BaseModel):
    """画面上の操作名と、操作ごとの追加payload。"""
    action: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """チャット送信内容。空文字判定はサービス層で行う。"""
    message: str
