"""ESPERのFastAPIバックエンド。

外部からはapp/create_appだけをimportすればよいように再公開する。
"""

from .main import app, create_app

__all__ = ["app", "create_app"]
