"""外部へ公開するデータ構造。

StateServiceやAPI層から参照する型エイリアスをまとめて再公開する。
"""

from .game_state import JsonValue, PublicGameState

__all__ = ["JsonValue", "PublicGameState"]
