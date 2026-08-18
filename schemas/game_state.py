"""ゲーム状態APIで使用するJSON互換型。

StateServiceが返す公開状態はブラウザへそのままJSONとして送るため、
値の型をJSONで表現できる範囲に限定している。
"""

from typing import TypeAlias


# 再帰的なJSON値型。dict/listの中もJsonValueだけにする。
JsonValue: TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)

# 公開状態全体はキー文字列、値JSON互換の辞書として扱う。
PublicGameState: TypeAlias = dict[str, JsonValue]
