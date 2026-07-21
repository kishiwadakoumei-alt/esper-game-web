"""ESPERアプリの起動処理と、対戦部屋の共有データを管理するモジュール。"""

# Fletは、PythonでWeb画面やデスクトップ画面を作るためのUIライブラリ。
import flet as ft
# 例外発生時に、エラーが起きた場所まで含む詳しい情報を表示するために使用する。
import traceback
# 実行環境からPORTなどの環境変数を取得するために使用する。
import os

# 画面の具体的な組み立てはui_views.pyに分離している。
# main.pyは「どの画面を最初に出すか」という入口だけを担当する。
from ui_views import show_title_screen, show_game_screen

# 対戦部屋を管理する辞書。
# キー   : プレイヤーが入力する合言葉（ルームID）
# 値     : その部屋専用のEsperGameオブジェクト
#
# main関数の外側で定義することで、同じPythonプロセスに接続した全プレイヤーから共有できる。
# ただし、サーバーを再起動すると内容は消え、複数プロセス構成ではプロセス間共有されない。
GAME_ROOMS = {}

def main(page: ft.Page):
    """プレイヤーがアプリへ接続するたびにFletから呼ばれる初期化関数。"""
    try:
        # pageは、現在接続している1人分の画面を表す。
        # ここで設定した値は、このプレイヤーの画面全体に適用される。
        page.bgcolor = "#222222"
        # 画面に収まらない場合は、縦方向へスクロールできるようにする。
        page.scroll = "auto"
        # ブラウザのタブなどに表示されるアプリ名。
        page.title = "超能力カードゲーム ESPER"

        # この接続だけが持つプレイヤー情報。
        # GAME_ROOMSが全員共有なのに対し、user_dataはプレイヤーごとに別の辞書となる。
        # roleには、入室時に先着順で"p1"または"p2"が設定される。
        user_data = {"name": "ゲスト", "room_id": "", "role": ""}
        
        # タイトル画面で入室処理が成功した後に呼ばれる画面切替用の関数。
        # user_dataとGAME_ROOMSを引数として固定し、タイトル画面側では引数なしで呼べるようにする。
        def go_to_game():
            show_game_screen(page, user_data, GAME_ROOMS)

        # 接続直後は、名前と合言葉を入力するタイトル画面を表示する。
        # go_to_gameも渡し、タイトル画面からゲーム画面へ遷移できるようにする。
        show_title_screen(page, user_data, GAME_ROOMS, go_to_game)

    except Exception as e:
        # 初期化中に予期しない例外が起きても、画面が真っ白にならないようにする。
        # traceback.format_exc()により、原因調査に必要なスタックトレースも表示する。
        page.add(ft.Text(f"システムエラー: {e}\n{traceback.format_exc()}", color="red"))
        page.update()

# デプロイ先が指定したPORT環境変数を使う。
# ローカル実行などでPORTが未設定の場合は8000番ポートを使う。
port = int(os.environ.get("PORT", 8000))
# mainを接続ごとの処理として登録し、全ネットワークインターフェースでWebサーバーを起動する。
# WEB_BROWSERを指定しているため、Fletアプリはブラウザ向けに提供される。
ft.app(main, port=port, view=ft.AppView.WEB_BROWSER, host="0.0.0.0")
