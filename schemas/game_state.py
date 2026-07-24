"""ゲーム状態APIで使用するJSON互換型。"""

from typing import TypeAlias


JsonValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)

PublicGameState: TypeAlias = dict[str, JsonValue]
