"""タイトル画面・ゲーム画面・各カード能力の操作UIを組み立てるモジュール。"""

# ボタン、テキスト、行・列などの画面部品を作るために使用する。
import flet as ft
# 「再生」でカードを山札へ戻した後、山札を再シャッフルするために使用する。
import random
# 手札に同じカードが何枚あるかを数え、使用可能な能力を判定するために使用する。
from collections import Counter
# 1部屋分の山札・手札・ターンなどを持つゲーム本体。
from game_logic import EsperGame

def show_title_screen(page: ft.Page, user_data: dict, GAME_ROOMS: dict, go_to_game):
    """名前と合言葉を入力し、2人用の対戦部屋へ入るタイトル画面を表示する。"""
    # 前に表示されていた部品をすべて削除し、タイトル画面を一から作り直す。
    page.controls.clear()
    
    # タイトル、プレイヤー名入力欄、ルームID入力欄を作る。
    # 同じroom_input.valueを入力した2人が同じ対戦部屋に参加する。
    title_text = ft.Text("🌟 超能力カードゲーム ESPER 🌐", size=32, weight="bold", color="orange")
    name_input = ft.TextField(label="あなたの名前", value="プレイヤー", width=300, bgcolor="#333333")
    
    # ★修正：「あいのことば」の誤字を修正
    room_input = ft.TextField(label="あいことば（ルームID）", hint_text="友達と同じ言葉を入れてね", width=300, bgcolor="#333333")
    
    def on_join_click(e):
        """入室ボタンが押されたとき、入力確認・部屋作成・役割決定を行う。"""
        # 合言葉が空では部屋を特定できないため、エラーを表示して処理を中断する。
        if not room_input.value:
            room_input.error_text = "あいことばを入力してください！"
            page.update()
            return
        
        # 入力値を、この接続専用のuser_dataへ保存する。
        # ゲーム画面へ遷移した後も、名前・部屋・roleを参照できる。
        user_data["name"] = name_input.value
        user_data["room_id"] = room_input.value
        
        # 同じ合言葉の部屋がまだなければ、新しいゲームを生成する。
        if user_data["room_id"] not in GAME_ROOMS:
            GAME_ROOMS[user_data["room_id"]] = EsperGame()
        
        # 入室先のEsperGameオブジェクトを取り出す。
        game = GAME_ROOMS[user_data["room_id"]]
        
        if len(game.players) == 0:
            # 最初に入室した人をp1（先攻）として登録する。
            user_data["role"] = "p1"
            game.players.append(user_data["name"])
        elif len(game.players) == 1:
            # 2人目をp2として登録し、待機状態から最初の捨て札操作へ進める。
            user_data["role"] = "p2"
            game.players.append(user_data["name"])
            game.turn_step = "DISCARD"
            game.log_message = f"対戦相手が見つかりました！ {game.players[0]} の先行で開始します。"
        else:
            # 3人目以降は参加させず、入力欄に満員エラーを表示する。
            room_input.error_text = "その部屋はすでに満員です！"
            page.update()
            return
        
        # 入室に成功したため、main.pyから渡された画面切替関数を呼ぶ。
        go_to_game()

    # on_clickに関数を渡すことで、クリック時にon_join_clickが実行される。
    join_btn = ft.Button("このあいことばで対戦部屋に入る 🚀", on_click=on_join_click, bgcolor="green", color="white", width=300, height=50)
    
    # Columnで部品を縦に並べ、外側のRowで画面中央へ配置する。
    # Containerは空白（スペーサー）としても使用している。
    page.add(
        ft.Row([
            ft.Column([
                ft.Container(height=50),
                title_text,
                ft.Container(height=20),
                name_input,
                room_input,
                ft.Container(height=10),
                join_btn
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ], alignment=ft.MainAxisAlignment.CENTER)
    )
    # controlsへの変更をブラウザへ反映する。
    page.update()

def show_game_screen(page: ft.Page, user_data: dict, GAME_ROOMS: dict):
    """入室済みプレイヤー向けに、対戦画面と全操作を表示する。"""
    # タイトル画面を消してからゲーム画面の描画を始める。
    page.controls.clear()
    page.update() 
    
    # user_dataに保存されたルームIDから、共有中のゲーム状態を取得する。
    game = GAME_ROOMS[user_data["room_id"]]
    # ログ表示で何度も使用するため、自分の名前を短い変数にしておく。
    my_name = user_data["name"]
    
    def on_message(topic, msg):
        """同じ部屋から更新通知を受けたとき、自分の画面を最新状態で再描画する。"""
        refresh()
        
    # ルームIDをPubSubのトピック名にすることで、別の部屋へ更新通知が混ざらないようにする。
    page.pubsub.subscribe_topic(user_data["room_id"], on_message)

    def sync():
        """同じ部屋にいる全画面へ、再描画を促すupdateメッセージを送る。"""
        page.pubsub.send_all_on_topic(user_data["room_id"], "update")

    # 2人そろってゲーム開始状態なら、先に入室して待っているp1の画面も更新する。
    if len(game.players) == 2 and game.turn_step == "DISCARD":
        sync()

    # 画面上部に常時表示する、自分の名前・プレイヤー番号・合言葉の情報欄。
    room_info = ft.Container(
        content=ft.Row([
            ft.Text(f"👤 {my_name} (プレイヤー{1 if user_data['role']=='p1' else 2})", color="white", weight="bold"),
            ft.Text(f"🔑 あいことば: {user_data['room_id']}", color="orange", weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=10, bgcolor="#333333", border_radius=5
    )

    def get_dashboard():
        """両者の捨て札と、ゲーム開始時に除外した3枚の表示領域を作る。"""

        def make_group_ui(group):
            """1回の行動で作られた捨て札1組を、少し重ねたカード表示に変換する。"""
            chips = []
            for idx, card_data in enumerate(group):
                # 裏向きでも、自分が捨てたカードなら自分の画面では内容を確認できる。
                is_mine = (user_data["role"] == card_data["owner"])
                show_name = card_data["name"] if (card_data["is_face_up"] or is_mine) else "？"
                
                if card_data["is_face_up"]:
                    # 表向きカードは明るい背景で全員にカード名を見せる。
                    color, bg = "black", "#E0E0E0"
                else:
                    # 裏向きカードは暗い背景にする。相手側ではshow_nameも「？」になる。
                    color, bg = "white", "#555555"
                    
                # leftとtopをカード番号ごとにずらし、複数枚を重なった束のように見せる。
                chips.append(
                    ft.Container(
                        content=ft.Text(show_name, color=color, weight="bold", size=10),
                        padding=5, 
                        bgcolor=bg, 
                        border_radius=5,
                        left=idx * 5,
                        top=idx * 5
                    )
                )
            # Stackは複数のContainerを同じ領域内で重ねて表示する。
            return ft.Stack(chips, width=60 + (len(group) * 5), height=50 + (len(group) * 5))

        # 自分と相手の捨て札グループを、現在のプレイヤー視点で取得する。
        my_groups = game.get_discard_groups(user_data["role"])
        op_groups = game.get_discard_groups(game.get_op_role(user_data["role"]))
        
        # 各グループをmake_group_uiで画面部品へ変換し、横並び・折り返し表示にする。
        my_dis_display = ft.Row([make_group_ui(g) for g in my_groups], wrap=True)
        op_dis_display = ft.Row([make_group_ui(g) for g in op_groups], wrap=True)
        
        # ゲーム開始時に除外された3枚の表示部品を作る。
        excluded_ui = []
        for card in game.excluded_cards:
            if getattr(game, "turn_step", "") in ["GAME_CLEAR", "GAME_OVER"]:
                # 決着後は除外カードの内容を公開する。
                excluded_ui.append(
                    ft.Container(content=ft.Text(card, color="black", weight="bold", size=10), padding=5, bgcolor="#E0E0E0", border_radius=5)
                )
            else:
                # 対戦中はカード名を伏せて「？」だけを表示する。
                excluded_ui.append(
                    ft.Container(content=ft.Text("？", color="white", weight="bold", size=10), padding=5, bgcolor="#555555", border_radius=5)
                )
        excluded_row = ft.Row(excluded_ui, wrap=True)
        
        # 捨て札と除外カードを1つの黒いダッシュボードにまとめて返す。
        return ft.Container(
            content=ft.Column([
                ft.Text("--- 捨て札エリア (公開情報) ---", color="white", weight="bold"),
                ft.Text(f"自分 ({len(my_groups)}組):", color="blue"), my_dis_display,
                ft.Text(f"相手 ({len(op_groups)}組):", color="red"), op_dis_display,
                ft.Divider(color="grey"),
                ft.Text("【ゲーム外】最初に除外された3枚:", color="yellow", weight="bold"),
                excluded_row
            ]), padding=10, bgcolor="#111111"
        )

    def refresh():
        """共有ゲーム状態のturn_stepに応じて、現在必要な画面部品をすべて作り直す。"""
        # ★追加：相手が退出して部屋が解散された場合の専用画面
        if getattr(game, "turn_step", "") == "ROOM_DISBANDED":
            def on_return_title(e):
                # 完全に通信を切り離し、タイトル画面へ戻る
                page.pubsub.unsubscribe_topic(user_data["room_id"], on_message)
                show_title_screen(page, user_data, GAME_ROOMS, go_to_game)
                
            page.controls.clear()
            page.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("対戦相手が退出したため、部屋が解散されました。", color="red", size=20, weight="bold"),
                        ft.Container(height=20),
                        ft.Button("タイトル画面に戻る", on_click=on_return_title, bgcolor="blue", color="white", width=300, height=50)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=50,
                    alignment=ft.alignment.center
                )
            )
            page.update()
            return
            
        # 毎回、新しい部品リストを作って最後にpage.controlsと入れ替える。
        new_controls = []
        new_controls.append(room_info)
        
        if game.turn_step == "WAITING":
            # p1だけ入室している状態では、部屋情報と待機メッセージだけを表示する。
            new_controls.append(ft.Text("対戦相手の入室を待っています... (友達にURLとあいことばを教えてね！)", color="yellow", size=20))
            page.controls.clear()
            page.controls.extend(new_controls)
            page.update()
            return

        # 対戦開始後は、どの操作段階でも共通して捨て札エリアを表示する。
        new_controls.append(get_dashboard())
        
        # 自分と相手のroleを、このプレイヤーの視点で決める。
        my_role = user_data["role"]
        op_role = game.get_op_role(my_role)
        
        # 自分の手札は見やすい順に並べたコピー、相手は枚数確認用の実データを取得する。
        display_my_hand = game.sort_hand(game.get_hand(my_role))
        display_op_hand = game.get_hand(op_role)
        
        # 相手の手札枚数と山札の残数を表示する。
        new_controls.append(ft.Text(f"相手の手札枚数: {len(display_op_hand)}枚 / 山札: {len(game.deck)}枚", color="red", weight="bold"))
        
        if game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
            new_controls.append(ft.Text("【公開された相手の手札】", color="red", weight="bold"))
            op_hand_row = ft.Row(wrap=True)
            # 相手の手札も見やすいようにソートして表示する
            sorted_op_hand = game.sort_hand(display_op_hand)
            for card in sorted_op_hand:
                op_hand_row.controls.append(ft.Button(card, disabled=True, bgcolor="#FFCDD2", color="black"))
            new_controls.append(op_hand_row)

        if game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
            # 決着メッセージは目立つオレンジ色・太字で表示する。
            new_controls.append(ft.Text(f"ログ: {game.log_message}", color="orange", size=18, weight="bold"))
        else:
            # 通常の進行ログは緑色で表示する。
            new_controls.append(ft.Text(f"ログ: {game.log_message}", color="green", size=16))
            
        # current_turnと自分のroleが一致しているときだけ、ゲーム操作を許可する。
        is_my_turn = (game.current_turn == my_role)
        
        # ゲーム中に手札が勝利条件を満たした場合だけ、エスパー宣言ボタンを表示する。
        if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"] and game.check_esper(display_my_hand):
            def on_esper_declare(e):
                # 宣言した時点で決着とし、勝利メッセージを両画面へ共有する。
                game.turn_step = "GAME_CLEAR"
                game.log_message = f"🎉【決着】{my_name} が「エスパー！」を宣言しました！🎉"
                sync()
            new_controls.append(
                ft.Button("🌟 エスパー宣言！ (同種5枚達成) 🌟", on_click=on_esper_declare, bgcolor="orange", color="black", width=400, height=50)
            )

        if not is_my_turn and game.turn_step not in ["GAME_CLEAR", "GAME_OVER"]:
            # 相手の手番中は自分のカードを確認できるが、ボタン操作は無効にする。
            new_controls.append(ft.Text("⏳ 相手の操作を待っています...", color="grey", size=18))
            hand_row = ft.Row(wrap=True)
            for card in display_my_hand:
                hand_row.controls.append(ft.Button(card, disabled=True, bgcolor="#CFD8DC", color="black"))
            new_controls.append(hand_row)
            
            if game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
                if my_role in getattr(game, "rematch_requests", set()):
                    # 自分がすでに再戦を押した場合は待機メッセージを出す。
                    new_controls.append(ft.Text("⏳ 相手の再戦承認を待っています...", color="cyan", weight="bold"))
                else:
                    def on_rematch_click(e):
                        """自分が再戦希望を出したことを記録し、両者揃えばリセットする。"""
                        game.rematch_requests.add(my_role)
                        if len(game.rematch_requests) == 2:
                            game.reset_game()
                        sync()
                        
                    def on_leave_click(e):
                        """自分が退室し、部屋を解散して相手にもタイトルへ戻るよう促す。"""
                        # 部屋を解散状態にする
                        game.turn_step = "ROOM_DISBANDED"
                        sync()
                        
                        # 共有データからこの部屋のデータを完全に削除する（同じIDで新しく作れるようにする）
                        if user_data["room_id"] in GAME_ROOMS:
                            del GAME_ROOMS[user_data["room_id"]]
                            
                        # 通信の受信を解除し、自分はタイトル画面に戻る
                        page.pubsub.unsubscribe_topic(user_data["room_id"], on_message)
                        show_title_screen(page, user_data, GAME_ROOMS, go_to_game)
                        
                    new_controls.append(
                        ft.Row([
                            ft.Button("もう一度対戦する 🔄", on_click=on_rematch_click, bgcolor="blue", color="white", height=50),
                            ft.Button("部屋を退出する 🚪", on_click=on_leave_click, bgcolor="red", color="white", height=50)
                        ])
                    )

            page.controls.clear()
            page.controls.extend(new_controls)
            page.update()
            return

        def route_ability(ability_name):
            """選択された能力名に応じて、次の操作段階と一時データを準備する。"""
            if ability_name == "瞬間移動":
                # 相手の手札から取り除きたいカード名を選ぶ段階へ進む。
                game.turn_step = "TELEPORT_SELECTION"
            elif ability_name == "念動力":
                if display_op_hand:
                    # 相手に手札があれば、捨てさせるカード位置の選択へ進む。
                    game.turn_step = "PSY_DISCARD_SELECTION"
                    game.log_message = "「念動力」発動！捨てる相手の手札を選んでください。"
                else:
                    # 対象がなければ能力効果なしとして、そのまま行動を終了する。
                    game.end_action(my_role, f"「念動力」発動！しかし相手の手札は空だった")
            elif ability_name == "再生":
                # 両者の捨て札が1枚でもあるかを確認する。
                flat_p1 = game.get_flat_discard("p1")
                flat_p2 = game.get_flat_discard("p2")
                if not flat_p1 and not flat_p2:
                    game.end_action(my_role, f"「ヒーリング」発動！しかし捨て札がなかった")
                else:
                    # 選択状態を初期化し、両者の全捨て札を選択候補へ変換する。
                    game.turn_step = "REGEN_SELECTION"
                    game.temp_selection = []
                    game.regen_pool = []
                    for g_idx, group in enumerate(game.get_discard_groups("p1")):
                        for item_idx, c in enumerate(group):
                            # 後で元の捨て札から正しく削除できるよう、グループ番号とカード番号も保存する。
                            game.regen_pool.append({"owner": "p1", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                    for g_idx, group in enumerate(game.get_discard_groups("p2")):
                        for item_idx, c in enumerate(group):
                            game.regen_pool.append({"owner": "p2", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                    game.log_message = "「ヒーリング」発動！山札に戻すカードを選んでください。"
            elif ability_name == "千里眼":
                if not display_op_hand:
                    # 相手の手札が空なら見る対象がないため、能力処理を終了する。
                    game.end_action(my_role, f"「千里眼」発動！しかし相手の手札は空だった")
                else:
                    # 最大2枚の手札位置を選ぶ段階へ進み、前回の選択内容を消す。
                    game.turn_step = "CLAIR_SELECTION"
                    game.temp_selection = []
                    game.log_message = "「千里眼」発動！透視する手札を選んでください。"
            elif ability_name == "未来予知":
                # 山札が3枚未満なら、残っている枚数だけを確認対象にする。
                count = min(3, len(game.deck))
                if count == 0:
                    game.end_action(my_role, f"「未来予知」発動！しかし山札が空だった")
                else:
                    # 山札の上側（この実装ではリスト末尾）からカードを一時的に取り出す。
                    game.prescience_cards = [game.deck.pop() for _ in range(count)]
                    game.prescience_ordered = []
                    game.turn_step = "PRESCIENCE_SELECT_1"
                    game.log_message = "「未来予知」発動！一番上に配置するカードを選んでください。"
            elif ability_name == "時間移動":
                # 次のend_actionで相手へ手番を渡さないため、追加ターンフラグを立てる。
                game.extra_turn = True
                # 能力発動で減った手札を6枚まで補充してから、行動を終了する。
                game.fill_hand_to_6(my_role)
                game.end_action(my_role, f"「時間移動」発動！{my_name} は追加ターンを得た")

        # 現在の操作段階に合わせて、手札欄の案内文を変える。
        if game.turn_step == "DISCARD":
            new_controls.append(ft.Text("【手札】 1枚選んで捨ててください", color="yellow"))
        elif game.turn_step == "DRAW":
            new_controls.append(ft.Text("【手札】 (現在は確認のみ・クリック不可)", color="grey"))
        elif game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
            new_controls.append(ft.Text("【自分の手札】", color="grey"))
        else:
            new_controls.append(ft.Text("【手札】 (現在は確認のみ・クリック不可)", color="grey"))

        # 自分の手札を1枚ずつボタンとして表示する。
        hand_row = ft.Row(wrap=True)
        for card in display_my_hand:
            def make_on_click(target_card=card):
                """ループ中のカード名を固定した、捨て札ボタン用の関数を作る。"""
                def on_click(e):
                    # DISCARD以外の段階では、手札ボタンを押しても何もしない。
                    if game.turn_step != "DISCARD": return
                    
                    # 表示用に並べ替えたリストではなく、ゲームが持つ本物の手札から削除する。
                    true_hand = game.get_hand(my_role)
                    true_hand.remove(target_card)
                    
                    # すでに自分が捨てた裏向きカードの総数を数える。
                    my_discard_groups = game.get_discard_groups(my_role)
                    face_down_count = sum(1 for g in my_discard_groups for c in g if not c["is_face_up"])
                    # 裏向きの捨て札が5枚に達した後は、新しい捨て札を表向きにする。
                    is_face_up = face_down_count >= 5
                    
                    # 通常の捨て札は1枚で1グループとし、所有者情報も一緒に保存する。
                    my_discard_groups.append([{"name": target_card, "is_face_up": is_face_up, "owner": my_role}])
                    
                    # 相手へカード名が漏れないよう、ログには捨てた人と枚数だけを表示する。
                    game.log_message = f"{my_name} がカードを1枚捨てました。山札から補充してください。"
                    # 次は山札から手札を6枚まで補充する段階。
                    game.turn_step = "DRAW"
                    sync()
                return on_click

            # 捨てる段階だけ白色、それ以外は操作不可に見える灰色で表示する。
            bg_color = "white" if game.turn_step == "DISCARD" else "#CFD8DC"
            hand_row.controls.append(ft.Button(card, on_click=make_on_click(card), color="black", bgcolor=bg_color))
        new_controls.append(hand_row)

        if game.turn_step == "DRAW":
            def on_draw(e):
                # 捨てて減った手札を6枚まで補充する。
                game.fill_hand_to_6(my_role)
                # 補充後は能力を使用するか選ぶ段階へ進む。
                game.turn_step = "THINK"
                game.log_message = f"{my_name} が手札を補充しました。能力を使いますか？"
                sync()
            
            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【補充】山札からカードを1枚引いてください", color="white", weight="bold"),
                    ft.Button("山札から引く", on_click=on_draw, bgcolor="blue", color="white")
                ]), padding=15, bgcolor="#224422", border_radius=5
            ))

        elif game.turn_step == "THINK":
            def on_go_ability(e):
                # 使用可能な能力を選ぶ画面へ進む。
                game.turn_step = "ABILITY"
                sync()

            def on_pass(e):
                # 能力を使わずに終了し、通常どおり相手へ手番を渡す。
                game.end_action(my_role, f"{my_name} は能力を使わずにターンを終了した")
                sync()

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【確認】新しい手札です。能力を使いますか？", color="white", size=16),
                    ft.Row([ft.Button("能力を使う", on_click=on_go_ability), ft.Button("ターン終了", on_click=on_pass)])
                ]), padding=15, bgcolor="#334433", border_radius=5
            ))

        elif game.turn_step == "ABILITY":
            # この段階では、手札から発動できる能力のボタン一覧を作る。
            decision_nodes = []
            # 同じ能力カードが2枚以上あれば、その能力を発動できる。
            counts = Counter(display_my_hand)
            # 擬態は専用処理があるため、通常能力一覧から除外する。
            usable_abilities = [c for c, cnt in counts.items() if cnt >= 2 and c != "擬態"]
            
            deck_len = len(game.deck)
                                
            def on_cancel(e):
                # 能力選択をやめ、能力を使うか再度選ぶ画面へ戻る。
                game.turn_step = "THINK"
                sync()
            decision_nodes.append(ft.Button("戻る", on_click=on_cancel))
            
            for ability in usable_abilities:
                def make_on_click(ab=ability):
                    """ループ中の能力名を固定した、能力発動ボタン用の関数を作る。"""
                    def on_ability_click(e):
                        # 能力のコストとして、同名カードを本物の手札から2枚取り除く。
                        true_hand = game.get_hand(my_role)
                        true_hand.remove(ab)
                        true_hand.remove(ab)
                        # 使用した2枚は表向きの1グループとして、自分の捨て札へ置く。
                        group = [
                            {"name": ab, "is_face_up": True, "owner": my_role},
                            {"name": ab, "is_face_up": True, "owner": my_role}
                        ]
                        game.get_discard_groups(my_role).append(group)
                        # 能力ごとの選択画面または即時効果へ処理を振り分ける。
                        route_ability(ab)
                        sync()
                    return on_ability_click
                
                is_disabled = False
                btn_text = f"【発動】{ability} (2枚)"
                if deck_len <= 1 and ability != "再生":
                    is_disabled = True
                    btn_text += " ⚠️山札1枚以下のため不可"
                decision_nodes.append(ft.Button(btn_text, on_click=make_on_click(ability), disabled=is_disabled))
            
            # 擬態が2枚以上あれば、擬態2枚＋他の能力1枚でその能力を代用できる。
            if counts.get("擬態", 0) >= 2:
                # setで重複を除き、代用先となる能力名を1種類ずつ表示する。
                other_cards = list(set([c for c in display_my_hand if c != "擬態"]))
                if other_cards:
                    def on_mimic_start_click(e):
                        # 擬態と一緒に捨てる能力カードを選ぶ段階へ進む。
                        game.turn_step = "MIMIC_SELECTION"
                        sync()
                        
                    can_mimic = (deck_len >= 3) or ("再生" in other_cards)
                    is_mimic_disabled = not can_mimic
                    mimic_text = "【発動】カモフラージュ (擬態2枚+1枚)"
                    
                    if is_mimic_disabled:
                        mimic_text += " ⚠️山札2枚以下のため不可"
                    elif deck_len <= 2:
                        mimic_text += " (再生のみ可能)"
                        
                    decision_nodes.append(ft.Button(mimic_text, on_click=on_mimic_start_click, disabled=is_mimic_disabled))
            
            new_controls.append(ft.Container(
                content=ft.Column([ft.Text("消費するペア：", color="white"), ft.Row(decision_nodes, wrap=True)]),
                padding=15, bgcolor="#333333", border_radius=5
            ))

        elif game.turn_step == "MIMIC_SELECTION":
            # 擬態で代用して発動する能力を、現在の手札から選ぶ。
            mimic_nodes = []
            other_cards = list(set([c for c in display_my_hand if c != "擬態"]))
            
            deck_len = len(game.deck) 
            
            for target in other_cards:
                def make_on_mimic_target(t=target):
                    """選択対象の能力名を固定した、擬態発動ボタン用の関数を作る。"""
                    def on_mimic_execute(e):
                        # コストとして擬態2枚と、代用先と同名のカード1枚を消費する。
                        true_hand = game.get_hand(my_role)
                        true_hand.remove("擬態")
                        true_hand.remove("擬態")
                        true_hand.remove(t)
                        # 消費した3枚は全員に見える表向きのグループとして捨てる。
                        group = [
                            {"name": "擬態", "is_face_up": True, "owner": my_role},
                            {"name": "擬態", "is_face_up": True, "owner": my_role},
                            {"name": t, "is_face_up": True, "owner": my_role}
                        ]
                        game.get_discard_groups(my_role).append(group)
                        # 選んだ通常カードの能力名で、通常と同じ能力処理へ進む。
                        route_ability(t)
                        sync()
                    return on_mimic_execute
                
                is_target_disabled = False
                target_text = f"{target} で発動"
                if deck_len <= 2 and target != "再生":
                    is_target_disabled = True
                    target_text += " ⚠️山札不足"
                    
                mimic_nodes.append(ft.Button(target_text, on_click=make_on_mimic_target(target), disabled=is_target_disabled))
            
            def on_cancel_mimic(e):
                # まだカードは消費していないため、そのまま通常の能力一覧へ戻れる。
                game.turn_step = "ABILITY"
                sync()
            mimic_nodes.append(ft.Button("キャンセル", on_click=on_cancel_mimic))
            
            new_controls.append(ft.Container(
                content=ft.Column([ft.Text("擬態2枚と一緒に捨てる手札：", color="white"), ft.Row(mimic_nodes, wrap=True)]),
                padding=15, bgcolor="#442222", border_radius=5
            ))

        elif game.turn_step == "TELEPORT_SELECTION":
            # 瞬間移動: 相手の手札から一括除去したいカード種類を宣言する。
            tel_nodes = []
            # 手札に存在するかどうかを知らなくても、全7種類から宣言できる。
            for t_name in game.types:
                def make_tel_click(target_name=t_name):
                    """宣言するカード名を固定した、瞬間移動ボタン用の関数を作る。"""
                    def on_tel_click(e):
                        true_op_hand = game.get_hand(op_role)
                        # 宣言した種類と一致する相手のカードをすべて抽出する。
                        removed = [c for c in true_op_hand if c == target_name]
                        
                        # 能力コストで減った自分の枚数と、除去後に減る相手の枚数を計算する。
                        my_needs = 6 - len(display_my_hand)
                        op_needs = 6 - (len(true_op_hand) - len(removed))
                        
                        # 両者を6枚へ補充できない場合は、処理を途中で変えず引き分け終了とする。
                        if (my_needs + op_needs) > len(game.deck):
                            msg = f"お互いに合計 {my_needs + op_needs} 枚の補充が必要ですが、山札が残り{len(game.deck)}枚のため補充できなくなりました"
                            game.trigger_draw(msg)
                            sync()
                            return
                            
                        # 相手の手札を、宣言した種類を除いた新しいリストへ置き換える。
                        game.set_hand(op_role, [c for c in true_op_hand if c != target_name])
                        
                        if removed:
                            # 除去できたカードは、相手所有の表向きグループとして相手の捨て札に置く。
                            group = [{"name": r, "is_face_up": True, "owner": op_role} for r in removed]
                            game.get_discard_groups(op_role).append(group)
                            
                        # 相手を6枚まで補充した後、能力コストで減った自分も6枚まで補充する。
                        for _ in range(op_needs):
                            if game.deck: game.get_hand(op_role).append(game.deck.pop())
                        game.fill_hand_to_6(my_role)
                        
                        # 除去できた実枚数を公開し、行動を終了する。
                        game.end_action(my_role, f"「テレポート」発動！{my_name} は【{target_name}】を指名し、相手の手札から {len(removed)} 枚捨てさせた！")
                        sync()
                    return on_tel_click
                tel_nodes.append(ft.Button(t_name, on_click=make_tel_click(t_name)))

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【テレポート】相手の手札から消し去るカード名（能力）を宣言してください：", color="white", weight="bold"),
                    ft.Row(tel_nodes, wrap=True)
                ]), padding=15, bgcolor="#332244", border_radius=5
            ))

        elif game.turn_step == "PSY_DISCARD_SELECTION":
            # 念動力 1段階目: 相手の手札を内容が見えない「位置」で1枚選び、捨てさせる。
            discard_nodes = []
            for idx, c in enumerate(display_op_hand):
                def make_discard_click(target_idx=idx, target_card=c):
                    """相手の手札番号を固定した、念動力の選択ボタン用関数を作る。"""
                    def on_discard_click(e):
                        true_op_hand = game.get_hand(op_role)
                        # 選ばれた位置のカードを相手の手札から取り除く。
                        discarded = true_op_hand.pop(target_idx)
                        op_groups = game.get_discard_groups(op_role)
                        # 取り除いたカードを、いったん表向きの捨て札として追加する。
                        op_groups.append([{"name": discarded, "is_face_up": True, "owner": op_role}])
                        
                        # 次の「押し付け」に使える、相手の裏向き捨て札を探す。
                        face_down_discards = [item for group in op_groups for item in group if not item["is_face_up"]]
                        
                        if not face_down_discards:
                            # 押し付けられる裏向き捨て札がなければ、追加した捨て札を取り消す。
                            op_groups.pop() 
                            # 選んだカードも相手の手札へ戻し、能力を不発として終了する。
                            true_op_hand.append(discarded)
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role, f"「念動力」発動！{my_name} は相手の 伏せカード {target_idx+1} を指定したが、相手の場に裏向きカードがないため手札に戻った")
                        else:
                            # 裏向き捨て札があれば、相手へ押し付けるカードを選ぶ2段階目へ進む。
                            game.log_message = f"「念動力」発動！{my_name} は相手の 伏せカード {target_idx+1} を捨てさせた！ 続けて押し付けるカードを選択中..."
                            game.turn_step = "PSY_PUSH_SELECTION"
                        sync()
                    return on_discard_click
                discard_nodes.append(ft.Button(f"伏せカード {idx+1}", on_click=make_discard_click(idx, c)))

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【念動力 1/2】相手の手札から捨てさせるカードを選んでください：", color="white", weight="bold"),
                    ft.Row(discard_nodes, wrap=True)
                ]), padding=15, bgcolor="#442244", border_radius=5
            ))

        elif game.turn_step == "PSY_PUSH_SELECTION":
            # 念動力 2段階目: 相手の裏向き捨て札を1枚、相手の手札へ戻す。
            psy_nodes = []
            
            # UI用番号だけでなく、元データ上のグループ番号・カード番号も記録する。
            face_down_discards = []
            op_groups = game.get_discard_groups(op_role)
            for g_idx, group in enumerate(op_groups):
                for item_idx, item in enumerate(group):
                    if not item["is_face_up"]:
                        face_down_discards.append((g_idx, item_idx, item))
                        
            for i, (g_idx, item_idx, target_item) in enumerate(face_down_discards):
                # i+1を、プレイヤーに見せる1始まりのカード番号として使う。
                def make_psy_click(t_g_idx=g_idx, t_item_idx=item_idx, t_name=target_item["name"], display_num=i+1):
                    def on_psy_click(e):
                        # 選ばれたカードを、元の捨て札グループから削除する。
                        op_groups[t_g_idx].pop(t_item_idx)
                        # カードがなくなった空グループは、グループごと削除する。
                        if not op_groups[t_g_idx]:
                            op_groups.pop(t_g_idx)
                            
                        # 捨て札から取り出したカードを相手の手札へ加える。
                        true_op_hand = game.get_hand(op_role)
                        true_op_hand.append(t_name)
                        # 能力コストで減った自分の手札を6枚まで補充する。
                        game.fill_hand_to_6(my_role)
                        game.end_action(my_role, f"{my_name} は続けて、相手に 裏向きの捨て札 {display_num} を押し付けた！")
                        sync()
                    return on_psy_click
                psy_nodes.append(ft.Button(f"裏向きの捨て札 {i+1}", on_click=make_psy_click(g_idx, item_idx, target_item["name"], i+1)))

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【念動力 2/2】相手の手札に加える裏向きの捨て札を選んでください：", color="white", weight="bold"),
                    ft.Row(psy_nodes, wrap=True)
                ]), padding=15, bgcolor="#224444", border_radius=5
            ))

        elif game.turn_step == "REGEN_SELECTION":
            # 再生: 両者の捨て札から最大3枚を選び、山札へ戻す。
            reg_nodes = []
            for list_idx, item in enumerate(game.regen_pool):
                # temp_selectionにはregen_pool内の番号を保存する。
                is_selected = list_idx in game.temp_selection
                def make_reg_click(target_idx=list_idx):
                    def on_reg_click(e):
                        # 選択済みを押すと解除、未選択なら3枚を上限として追加する。
                        if target_idx in game.temp_selection: game.temp_selection.remove(target_idx)
                        elif len(game.temp_selection) < 3: game.temp_selection.append(target_idx)
                        sync()
                    return on_reg_click
                
                prefix = "自分" if item["owner"] == my_role else "相手"
                is_mine = (my_role == item["owner"])
                # 裏向きでも自分の捨て札なら名前を表示し、相手のものは「？」にする。
                show_name = item["name"] if (item["is_face_up"] or is_mine) else "？"
                display_text = f"【{prefix}】{show_name}" if item["is_face_up"] else f"【{prefix}】裏向き({show_name})"
                bg_color = "orange" if is_selected else ("#E0E0E0" if item["is_face_up"] else "#555555")
                text_color = "black" if (is_selected or item["is_face_up"]) else "white"
                reg_nodes.append(ft.Button(display_text, on_click=make_reg_click(list_idx), bgcolor=bg_color, color=text_color))
            
            def on_confirm_reg(e):
                """選択した捨て札を元の場所から取り除き、山札へ戻して能力を完了する。"""
                selected_items = [game.regen_pool[i] for i in game.temp_selection]
                
                # ログへ表示するため、選択カードの所有者・向き・公開可能な名前をまとめる。
                returned_info = []
                for item in selected_items:
                    owner_str = "自分" if item["owner"] == my_role else "相手"
                    if item["is_face_up"]:
                        returned_info.append(f"【{owner_str}】の表向き({item['name']})")
                    else:
                        returned_info.append(f"【{owner_str}】の裏向きカード")
                joined_info = "、".join(returned_info)
                
                # 同じグループから複数枚消す際に番号ずれを起こさないため、後ろ側から削除する。
                def get_sort_key(item): return (item["g_idx"], item["item_idx"])
                
                p1_items = sorted([item for item in selected_items if item["owner"] == "p1"], key=get_sort_key, reverse=True)
                p2_items = sorted([item for item in selected_items if item["owner"] == "p2"], key=get_sort_key, reverse=True)
                
                for item in p1_items:
                    # p1の捨て札からカードを取り出し、名前だけを山札へ戻す。
                    game.deck.append(game.p1_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                    # 取り出した結果空になったグループは削除する。
                    if not game.p1_discard_groups[item["g_idx"]]: game.p1_discard_groups.pop(item["g_idx"])
                        
                for item in p2_items:
                    # p2側もp1側と同じ手順で処理する。
                    game.deck.append(game.p2_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                    if not game.p2_discard_groups[item["g_idx"]]: game.p2_discard_groups.pop(item["g_idx"])
                
                # 戻したカードの場所が分からないよう、山札全体をシャッフルする。
                random.shuffle(game.deck)
                # 再生のコストで減った自分の手札を6枚まで補充する。
                game.fill_hand_to_6(my_role)
                
                # 1枚以上戻した場合と、0枚のまま確定した場合でログを分ける。
                if joined_info:
                    game.end_action(my_role, f"「ヒーリング」発動！{my_name} は捨て札から {joined_info} を山札に戻してシャッフルした")
                else:
                    game.end_action(my_role, f"「ヒーリング」発動！しかし {my_name} は何も戻さなかった")
                    
                # 次回の能力発動へ選択内容を持ち越さないよう初期化する。
                game.temp_selection = []
                sync()

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text(f"【再生】山札に戻すカードを選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                    ft.Row(reg_nodes, wrap=True),
                    ft.Button("選択完了", on_click=on_confirm_reg, bgcolor="blue", color="white")
                ]), padding=15, bgcolor="#224422", border_radius=5
            ))

        elif game.turn_step == "CLAIR_SELECTION":
            # 千里眼 1段階目: 内容を見たい相手の手札位置を最大2枚選ぶ。
            clair_nodes = []
            for idx, c in enumerate(display_op_hand):
                is_selected = idx in game.temp_selection
                def make_clair_click(target_idx=idx):
                    def on_clair_click(e):
                        # 選択済みなら解除し、未選択なら2枚を上限として追加する。
                        if target_idx in game.temp_selection: game.temp_selection.remove(target_idx)
                        elif len(game.temp_selection) < 2: game.temp_selection.append(target_idx)
                        sync()
                    return on_clair_click
                bg_color = "orange" if is_selected else "#555555"
                text_color = "black" if is_selected else "white"
                clair_nodes.append(ft.Button(f"伏せカード {idx+1}", on_click=make_clair_click(idx), bgcolor=bg_color, color=text_color))
            
            def on_confirm_clair(e):
                # 選択したカードの中身を表示する確認段階へ進む。
                game.turn_step = "CLAIR_REVEAL"
                # 選択番号だけを共有状態に保持し、再描画時に該当カードだけ公開する。
                game.log_message = f"「千里眼」発動！透視結果を確認中..."
                sync()

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text(f"【千里眼】中身を見たい相手の手札を最大2枚まで選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                    ft.Row(clair_nodes, wrap=True),
                    ft.Button("選択完了", on_click=on_confirm_clair, bgcolor="blue", color="white")
                ]), padding=15, bgcolor="#222266", border_radius=5
            ))

        elif game.turn_step == "CLAIR_REVEAL":
            # 千里眼 2段階目: 選択した位置のカード名だけを表示する。
            reveal_nodes = []
            for idx, c in enumerate(display_op_hand):
                if idx in game.temp_selection:
                    # 選んだ位置は、実際の相手のカード名を表示する。
                    reveal_nodes.append(ft.Button(f"【透視】{c}", bgcolor="white", color="red"))
                else:
                    # 選ばなかった位置は伏せたまま、操作不能ボタンとして表示する。
                    reveal_nodes.append(ft.Button(f"伏せカード {idx+1}", bgcolor="#555555", color="white", disabled=True))
                    
            def on_clair_done(e):
                # 公開したカード名そのものはログへ残さず、見た位置だけを記録する。
                looked_cards = " と ".join([f"伏せカード {idx+1}" for idx in sorted(game.temp_selection)])
                # 透視結果を消し、能力コスト分を補充してターンを終える。
                game.temp_selection = []
                game.fill_hand_to_6(my_role)
                game.end_action(my_role, f"「千里眼」発動！{my_name} は相手の {looked_cards} を透視した！")
                sync()

            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【千里眼】透視結果です。確認したら完了ボタンを押してください。", color="white", weight="bold"),
                    ft.Row(reveal_nodes, wrap=True),
                    ft.Button("確認完了", on_click=on_clair_done, bgcolor="blue", color="white")
                ]), padding=15, bgcolor="#222266", border_radius=5
            ))

        elif game.turn_step == "PRESCIENCE_SELECT_1":
            # 未来予知 1段階目: 山札から一時的に取り出した最大3枚のうち、1枚目を選ぶ。
            nodes = []
            for idx, c in enumerate(game.prescience_cards):
                def make_click(target_idx=idx, card_name=c):
                    """候補の位置とカード名を固定した、未来予知の選択関数を作る。"""
                    def on_click(e):
                        # 選んだカード名を順序付きリストへ追加し、未選択候補から取り除く。
                        game.prescience_ordered.append(card_name)
                        game.prescience_cards.pop(target_idx)
                        # まだ2枚目を選べる場合は、2段階目の選択画面へ進む。
                        if len(game.prescience_ordered) < 2 and game.prescience_cards:
                            game.turn_step = "PRESCIENCE_SELECT_2"
                        else:
                            # 候補が1枚しかなかった場合は、その1枚を手札へ加えて処理を完了する。
                            true_hand = game.get_hand(my_role)
                            true_hand.extend(game.prescience_ordered)
                            # 選択カードだけで6枚に満たなければ、通常どおり山札から追加補充する。
                            game.fill_hand_to_6(my_role)
                            # 選ばなかった確認済みカードは山札へ戻す。
                            for card in game.prescience_cards:
                                game.deck.append(card)
                            # 次回発動に備え、未来予知用の一時データを空にする。
                            game.prescience_ordered = []
                            game.prescience_cards = []
                            game.end_action(my_role, f"「未来予知」発動！{my_name} は未来を覗き見た！")
                        sync()
                    return on_click
                nodes.append(ft.Button(c, on_click=make_click(idx)))
            
            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【未来予知 1/2】一番上（次に引くカード）を選んでください：", color="white", weight="bold"),
                    ft.Row(nodes, wrap=True)
                ]), padding=15, bgcolor="#666622", border_radius=5
            ))

        elif game.turn_step == "PRESCIENCE_SELECT_2":
            # 未来予知 2段階目: 残りの候補から2枚目を選ぶ。
            nodes = []
            for idx, c in enumerate(game.prescience_cards):
                def make_click(target_idx=idx, card_name=c):
                    def on_click(e):
                        # 2枚目を選択済みリストへ移す。
                        game.prescience_ordered.append(card_name)
                        game.prescience_cards.pop(target_idx)
                        
                        # 実装上、選んだ2枚は山札の上へ並べるのではなく、現在の手札へ直接加える。
                        true_hand = game.get_hand(my_role)
                        true_hand.extend(game.prescience_ordered)
                        # それでも6枚未満なら、山札から通常補充する。
                        game.fill_hand_to_6(my_role)
                        # 最後まで選ばれなかったカードは山札へ戻す。
                        for card in game.prescience_cards:
                            game.deck.append(card)
                            
                        # 未来予知用の一時データを初期化し、行動を終了する。
                        game.prescience_ordered = []
                        game.prescience_cards = []
                        game.end_action(my_role, f"「未来予知」発動！{my_name} は未来を覗き見た！")
                        sync()
                    return on_click
                nodes.append(ft.Button(c, on_click=make_click(idx)))
                
            new_controls.append(ft.Container(
                content=ft.Column([
                    ft.Text("【未来予知 2/2】山札の2枚目にしたいカードを選んでください：", color="white", weight="bold"),
                    ft.Row(nodes, wrap=True)
                ]), padding=15, bgcolor="#666622", border_radius=5
            ))

        # ★追加：ゲーム終了時専用の「再戦 / 退室」ボタン領域
        if getattr(game, "turn_step", "") in ["GAME_CLEAR", "GAME_OVER"]:
            if my_role in getattr(game, "rematch_requests", set()):
                # 自分がすでに再戦を押した場合は待機メッセージを出す。
                new_controls.append(ft.Text("⏳ 相手の再戦承認を待っています...", color="cyan", weight="bold"))
            else:
                def on_rematch_click(e):
                    """自分が再戦希望を出したことを記録し、両者揃えばリセットする。"""
                    game.rematch_requests.add(my_role)
                    if len(game.rematch_requests) == 2:
                        game.reset_game()
                    sync()
                    
                def on_leave_click(e):
                    """自分が退室し、部屋を解散して相手にもタイトルへ戻るよう促す。"""
                    # 部屋を解散状態にする
                    game.turn_step = "ROOM_DISBANDED"
                    sync()
                    
                    # 共有データからこの部屋のデータを完全に削除する（同じIDで新しく作れるようにする）
                    if user_data["room_id"] in GAME_ROOMS:
                        del GAME_ROOMS[user_data["room_id"]]
                        
                    # 通信の受信を解除し、自分はタイトル画面に戻る
                    page.pubsub.unsubscribe_topic(user_data["room_id"], on_message)
                    show_title_screen(page, user_data, GAME_ROOMS, go_to_game)
                    
                new_controls.append(
                    ft.Row([
                        ft.Button("もう一度対戦する 🔄", on_click=on_rematch_click, bgcolor="blue", color="white", height=50),
                        ft.Button("部屋を退出する 🚪", on_click=on_leave_click, bgcolor="red", color="white", height=50)
                    ])
                )

        # このturn_step用に作った全画面部品で、現在の画面を丸ごと置き換える。
        page.controls.clear()
        page.controls.extend(new_controls)
        # 変更内容をブラウザへ反映する。
        page.update()

    # ゲーム画面へ入った直後の初回描画を実行する。
    refresh()