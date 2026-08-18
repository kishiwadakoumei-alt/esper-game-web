"""ESPER FastAPIアプリケーションの起動エントリーポイント。

ローカル実行やホスティング環境から `python3 main.py` で起動される薄いラッパー。
アプリ本体は backend.main.create_app で作る。
"""

import os

import uvicorn

from backend.main import app


def main() -> None:
    """環境変数PORTを使用してWebサーバーを起動する。

    PORTが未設定なら開発用に8000番で待ち受ける。
    """
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
