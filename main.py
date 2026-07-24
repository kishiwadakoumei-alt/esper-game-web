"""ESPER FastAPIアプリケーションの起動エントリーポイント。"""

import os

import uvicorn

from backend.main import app


def main() -> None:
    """環境変数PORTを使用してWebサーバーを起動する。"""
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
