import flet as ft
import traceback
import os

# 作成した2つのファイルから、ルールと見た目の関数をインポート（呼び出し）します
from ui_views import show_title_screen, show_game_screen

# 部屋を管理する辞書（全プレイヤーで共有）
GAME_ROOMS = {}

def main(page: ft.Page):
    try:
        # アプリ全体の設定
        page.bgcolor = "#222222"
        page.scroll = "auto"
        page.title = "超能力カードゲーム ESPER"

        # プレイヤー個人の情報（名前、入っている部屋、p1かp2か）
        user_data = {"name": "ゲスト", "room_id": "", "role": ""}
        
        # タイトル画面からゲーム画面へ切り替えるための橋渡し関数
        def go_to_game():
            show_game_screen(page, user_data, GAME_ROOMS)

        # 最初にタイトル画面を表示する指示を出す
        show_title_screen(page, user_data, GAME_ROOMS, go_to_game)

    except Exception as e:
        page.add(ft.Text(f"システムエラー: {e}\n{traceback.format_exc()}", color="red"))
        page.update()

# サーバー起動用のおまじない
port = int(os.environ.get("PORT", 8000))
ft.app(main, port=port, view=ft.AppView.WEB_BROWSER, host="0.0.0.0")