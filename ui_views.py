"""タイトル画面・ゲーム画面・各カード能力の操作UIを組み立てるモジュール。"""

import flet as ft
from collections import Counter
import threading
import time
from services import CpuService, GameService, RoomService
from services.game_service import NAME_MAP

def show_title_screen(page: ft.Page, user_data: dict, GAME_ROOMS: dict, go_to_game):
    page.controls.clear()
    
    title_text = ft.Text("🌟 超能力カードゲーム ESPER 🌐", size=24, weight="bold", color="orange", text_align=ft.TextAlign.CENTER)
    name_input = ft.TextField(label="あなたの名前", value="プレイヤー", width=300, bgcolor="#333333")
    room_input = ft.TextField(label="あいことば（ルームID）", hint_text="友達と同じ言葉を入れてね", width=300, bgcolor="#333333")
    
    def on_join_click(e):
        if not room_input.value:
            room_input.error_text = "あいことばを入力してください！"
            page.update()
            return
        
        user_data["name"] = name_input.value
        user_data["room_id"] = room_input.value
        user_data["has_left"] = False
        
        result = RoomService.join_room(
            GAME_ROOMS,
            user_data["room_id"],
            user_data["name"],
        )
        if result.error:
            room_input.error_text = result.error
            page.update()
            return

        user_data["role"] = result.role
        go_to_game()

    def start_cpu_game(level, name_suffix):
        user_data["name"] = name_input.value
        user_data["has_left"] = False
        user_data["role"] = "p1"
        user_data["room_id"], _ = RoomService.create_cpu_room(
            GAME_ROOMS,
            user_data["name"],
            level,
            name_suffix,
        )
        go_to_game()

    def on_cpu_easy(e): start_cpu_game("easy", "初級")
    def on_cpu_normal(e): start_cpu_game("normal", "中級")
    def on_cpu_hard(e): start_cpu_game("hard", "上級")

    join_btn = ft.Button("このあいことばで対戦部屋に入る 🚀", on_click=on_join_click, bgcolor="green", color="white", width=300, height=50)
    cpu_easy_btn = ft.Button("１人プレイ（vs CPU 初級） 🔰", on_click=on_cpu_easy, bgcolor="cyan", color="black", width=300)
    cpu_normal_btn = ft.Button("１人プレイ（vs CPU 中級） 🤖", on_click=on_cpu_normal, bgcolor="blue", color="white", width=300)
    cpu_hard_btn = ft.Button("１人プレイ（vs CPU 上級） 👹", on_click=on_cpu_hard, bgcolor="purple", color="white", width=300)
    
    # 画面が右にズレる・エラーになる原因だった Row や Containerのalignment を外し、
    # 縦並び（Column）の中央揃えだけでシンプルに配置します。
    page.add(
        ft.Column([
            ft.Container(height=50), title_text, ft.Container(height=20),
            name_input, 
            ft.Divider(color="grey"),
            room_input, join_btn,
            ft.Divider(color="grey"),
            cpu_easy_btn, cpu_normal_btn, cpu_hard_btn
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )
    page.update()

def show_game_screen(page: ft.Page, user_data: dict, GAME_ROOMS: dict):
    def go_to_game():
        show_game_screen(page, user_data, GAME_ROOMS)

    page.controls.clear()
    page.update() 
    
    game = GAME_ROOMS[user_data["room_id"]]
    my_name = user_data["name"]
    my_role = user_data["role"]
    
    def on_message(topic, msg):
        refresh()
        
    page.pubsub.subscribe_topic(user_data["room_id"], on_message)

    def sync():
        page.pubsub.send_all_on_topic(user_data["room_id"], "update")

    cpu_active_steps = CpuService.ACTIVE_STEPS
    if len(game.players) == 2 and game.turn_step in ["DECIDING_TURN"] + cpu_active_steps:
        sync()

    room_info = ft.Container(
        content=ft.Row([
            ft.Text(f"👤 {my_name} (プレイヤー{1 if my_role=='p1' else 2})", color="white", weight="bold"),
            ft.Text(f"🔑 あいことば: {user_data['room_id']}", color="orange", weight="bold"),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=10, bgcolor="#333333", border_radius=5
    )

    help_panel = ft.ExpansionTile(
        title=ft.Text("❓ 能力一覧（タップして開く）", color="yellow", weight="bold"),
        affinity=ft.TileAffinity.LEADING,
        collapsed_bgcolor="#222222", bgcolor="#333333",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("• クレヤボヤンス(千里眼)：相手の手札または相手の場にある裏向きのカードの中から２枚選び見る。", color="white"),
                    ft.Text("• タイムリープ(時間移動)：このターンの後にもう１度自分のターンを行う。そのターン中も能力は使える。", color="white"),
                    ft.Text("• サイコキネシス(念力)：相手の手札を１枚選び表向きで捨てさせ相手の裏向きのカードから１枚選び手札に戻す。ただし、重なっているカードは手札に戻せない。", color="white"),
                    ft.Text("• プリサイエンス(未来予知)：山札の上から３枚みて好きな順番に変えて戻す。", color="white"),
                    ft.Text("• テレポート(瞬間移動)：好きな能力を１つ宣言する。相手は手札にあるその能力のカードをすべて捨てる。", color="white"),
                    ft.Text("• ヒーリング(再生)：場にあるカードを３枚まで選び、山札に加えてシャッフルする。このとき裏向きのカードも選べる。", color="white"),
                    ft.Text("• カモフラージュ(擬態)：このターン中のみ好きなカード１枚として使える。そのカードで更に能力を発動でき、エスパー宣言もできる。", color="white"),
                ]), padding=10
            )
        ]
    )

    def get_log_ui():
        latest_text = game.log_message if hasattr(game, "log_message") else ""
        history_controls = []
        for log in getattr(game, "log_history", [])[::-1]:
            text_color = "cyan" if log["role"] == "p1" else ("pink" if log["role"] == "p2" else "yellow")
            history_controls.append(ft.Text(f"[{log['time']}] {log['icon']} {log['name']}: {log['text']}", color=text_color, size=14))
            
        return ft.ExpansionTile(
            title=ft.Text(f"📜 最新ログ: {latest_text}", color="white", weight="bold"),
            subtitle=ft.Text("タップで過去のログ履歴を展開", color="grey", size=12),
            affinity=ft.TileAffinity.LEADING,
            collapsed_bgcolor="#111133", bgcolor="#111122",
            controls=[
                ft.Container(content=ft.Column(history_controls, spacing=2, scroll=ft.ScrollMode.AUTO), height=200, padding=10)
            ]
        )

    def get_dashboard():
        def make_group_ui(group):
            chips = []
            for idx, card_data in enumerate(group):
                is_mine = (user_data["role"] == card_data["owner"])
                show_name = card_data["name"] if (card_data["is_face_up"] or is_mine) else "？"
                color, bg = ("black", "#E0E0E0") if card_data["is_face_up"] else ("white", "#555555")
                chips.append(
                    ft.Container(
                        content=ft.Text(show_name, color=color, weight="bold", size=10),
                        padding=5,
                        bgcolor=bg, border_radius=4, left=idx * 6, top=idx * 6
                    )
                )
            return ft.Stack(chips, width=80 + (len(group) * 6), height=40 + (len(group) * 6))

        my_groups = game.get_discard_groups(user_data["role"])
        op_groups = game.get_discard_groups(game.get_op_role(user_data["role"]))
        
        my_dis_display = ft.Row([make_group_ui(g) for g in my_groups], wrap=True)
        op_dis_display = ft.Row([make_group_ui(g) for g in op_groups], wrap=True)
        
        excluded_ui = []
        for card in game.excluded_cards:
            if getattr(game, "turn_step", "") in ["GAME_CLEAR", "GAME_OVER"]:
                excluded_ui.append(ft.Container(content=ft.Text(card, color="black", weight="bold", size=10), padding=5, bgcolor="#E0E0E0", border_radius=5))
            else:
                excluded_ui.append(ft.Container(content=ft.Text("？", color="white", weight="bold", size=10), padding=5, bgcolor="#555555", border_radius=5))
        
        return ft.Container(
            content=ft.Column([
                ft.Text("--- 捨て札エリア (公開情報) ---", color="white", weight="bold"),
                ft.Text(f"自分 ({len(my_groups)}組):", color="blue"), my_dis_display,
                ft.Text(f"相手 ({len(op_groups)}組):", color="red"), op_dis_display,
                ft.Divider(color="grey"),
                ft.Text("【ゲーム外】最初に除外された３枚:", color="yellow", weight="bold"),
                ft.Row(excluded_ui, wrap=True)
            ]), padding=10, bgcolor="#111111"
        )

    def refresh():
        if user_data.get("has_left"):
            return
            
        if getattr(game, "turn_step", "") == "ROOM_DISBANDED":
            def on_return_title(e):
                page.pubsub.unsubscribe_topic(user_data["room_id"])
                show_title_screen(page, user_data, GAME_ROOMS, go_to_game)
                
            page.controls.clear()
            # エラー防止のため、ここも Column のみで中央揃えします
            page.controls.append(
                ft.Column([
                    ft.Container(height=100),
                    ft.Text("対戦が終了し、部屋が解散されました。", color="red", size=20, weight="bold", text_align=ft.TextAlign.CENTER),
                    ft.Container(height=20),
                    ft.Button("タイトル画面に戻る", on_click=on_return_title, bgcolor="blue", color="white", width=300, height=50)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
            page.update()
            return

        # CPUの判断と状態変更はサービス層で行い、UIは待機と同期だけを担当する。
        if CpuService.begin_action(game):
            def run_cpu():
                time.sleep(1.0)
                try:
                    CpuService.take_step(game)
                finally:
                    CpuService.finish_action(game)
                    sync()

            threading.Thread(target=run_cpu).start()

        new_controls = [room_info, help_panel]
        
        if game.turn_step == "WAITING":
            new_controls.append(ft.Text("対戦相手の入室を待っています... (友達にURLとあいことばを教えてね！)", color="yellow", size=20))
            page.controls.clear()
            page.controls.extend(new_controls)
            page.update()
            return

        if game.turn_step == "DECIDING_TURN":
            def execute_roulette():
                time.sleep(1.5)
                GameService.decide_first_player(game)
                sync()

            if my_role == "p1" and GameService.start_turn_timer(game):
                threading.Thread(target=execute_roulette).start()

            # エラー防止のため、ここも Column のみで中央揃えします
            new_controls.append(
                ft.Column([
                    ft.Container(height=100),
                    ft.ProgressRing(color="orange"),
                    ft.Text("🎲 先攻・後攻 コイントス抽選中...", color="orange", size=24, weight="bold", text_align=ft.TextAlign.CENTER)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
            )
            page.controls.clear()
            page.controls.extend(new_controls)
            page.update()
            return

        new_controls.append(get_log_ui())
        new_controls.append(get_dashboard())
        
        op_role = game.get_op_role(my_role)
        display_my_hand = game.sort_hand(game.get_hand(my_role))
        
        true_op_hand = game.get_hand(op_role)
        display_op_hand = game.sort_hand(true_op_hand)
        
        new_controls.append(ft.Text(f"相手の手札枚数: {len(true_op_hand)}枚 / 山札: {len(game.deck)}枚", color="red", weight="bold"))
        
        if game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
            new_controls.append(ft.Text(game.log_message, color="orange", size=20, weight="bold"))
            new_controls.append(ft.Text("【公開された相手の手札】", color="red", weight="bold"))
            op_hand_row = ft.Row(wrap=True)
            for card in display_op_hand:
                op_hand_row.controls.append(
                    ft.Container(
                        content=ft.Text(card, size=12, weight="bold", color="black"),
                        bgcolor="#FFCDD2", padding=5, border_radius=5
                    )
                )
            new_controls.append(op_hand_row)
            
            RoomService.accept_cpu_rematch(game)
            
        is_my_turn = (game.current_turn == my_role)
        
        if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"] and game.check_esper(display_my_hand):
            def on_esper_declare(e):
                GameService.declare_esper(game, my_role, my_name)
                sync()
            new_controls.append(ft.Button("🌟 エスパー宣言！ (同種５枚達成) 🌟", on_click=on_esper_declare, bgcolor="orange", color="black", width=400, height=50))

        if not is_my_turn and game.turn_step not in ["GAME_CLEAR", "GAME_OVER"]:
            new_controls.append(ft.Text("⏳ 相手の操作を待っています...", color="grey", size=18))
            hand_row = ft.Row(wrap=True)
            for card in display_my_hand:
                hand_row.controls.append(
                    ft.Container(
                        content=ft.Text(card, size=12, weight="bold", color="black"),
                        bgcolor="#CFD8DC", padding=5, border_radius=5
                    )
                )
            new_controls.append(hand_row)

        else:
            if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"]:
                new_controls.append(ft.Text(f"ログ: {game.log_message}", color="green", size=16))

            if game.turn_step == "DISCARD":
                new_controls.append(ft.Text("【手札】 １枚選んで捨ててください", color="yellow"))
            elif game.turn_step == "DRAW":
                new_controls.append(ft.Text("【手札】 (現在は確認のみ・クリック不可)", color="grey"))
            elif game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
                pass
            else:
                new_controls.append(ft.Text("【手札】 (現在は確認のみ・クリック不可)", color="grey"))

            hand_row = ft.Row(wrap=True)
            for card in display_my_hand:
                def make_on_click(target_card=card):
                    def on_click(e):
                        if game.turn_step != "DISCARD": return
                        GameService.discard_card(
                            game,
                            my_role,
                            target_card,
                            my_name,
                        )
                        sync()
                    return on_click

                bg_color = "white" if game.turn_step == "DISCARD" else "#CFD8DC"
                hand_row.controls.append(
                    ft.Container(
                        content=ft.Text(card, size=12, weight="bold", color="black"),
                        bgcolor=bg_color, padding=5,
                        border_radius=5, ink=True,
                        on_click=make_on_click(card) if game.turn_step == "DISCARD" else None
                    )
                )
            new_controls.append(hand_row)

            if game.turn_step == "DRAW":
                def on_draw(e):
                    GameService.draw_hand(game, my_role, my_name)
                    sync()
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【補充】山札からカードを１枚引いてください", color="white", weight="bold"),
                        ft.Button("山札から引く", on_click=on_draw, bgcolor="blue", color="white")
                    ]), padding=15, bgcolor="#224422", border_radius=5
                ))

            elif game.turn_step == "THINK":
                def on_go_ability(e):
                    GameService.open_ability_selection(game)
                    sync()
                def on_pass(e):
                    GameService.pass_turn(game, my_role, my_name)
                    sync()
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【確認】新しい手札です。能力を使いますか？", color="white", size=16),
                        ft.Row([ft.Button("能力を使う", on_click=on_go_ability), ft.Button("ターン終了", on_click=on_pass)])
                    ]), padding=15, bgcolor="#334433", border_radius=5
                ))

            elif game.turn_step == "ABILITY":
                decision_nodes = []
                counts = Counter(display_my_hand)
                usable_abilities = [c for c, cnt in counts.items() if cnt >= 2 and c != "カモフラージュ"]
                deck_len = len(game.deck)
                                    
                def on_cancel(e):
                    GameService.cancel_ability_selection(game)
                    sync()
                decision_nodes.append(ft.Button("戻る", on_click=on_cancel))
                
                for ability in usable_abilities:
                    def make_on_click(ab=ability):
                        def on_ability_click(e):
                            GameService.activate_ability(
                                game,
                                my_role,
                                ab,
                                my_name,
                            )
                            sync()
                        return on_ability_click
                    
                    is_disabled = False
                    ab_display = NAME_MAP.get(ability, ability)
                    btn_text = f"【発動】{ab_display} (２枚)"
                    if deck_len <= 1 and ability != "ヒーリング":
                        is_disabled = True
                        btn_text += " ⚠️山札１枚以下のため不可"
                    decision_nodes.append(ft.Button(btn_text, on_click=make_on_click(ability), disabled=is_disabled))
                
                if counts.get("カモフラージュ", 0) >= 2:
                    other_cards = list(set([c for c in display_my_hand if c != "カモフラージュ"]))
                    if other_cards:
                        def on_mimic_start_click(e):
                            GameService.open_mimic_selection(game)
                            sync()
                        can_mimic = (deck_len >= 3) or ("ヒーリング" in other_cards)
                        is_mimic_disabled = not can_mimic
                        mimic_text = "【発動】カモフラージュ(擬態) (２枚+１枚)"
                        if is_mimic_disabled: mimic_text += " ⚠️山札２枚以下のため不可"
                        elif deck_len <= 2: mimic_text += " (ヒーリングのみ可能)"
                        decision_nodes.append(ft.Button(mimic_text, on_click=on_mimic_start_click, disabled=is_mimic_disabled))
                
                new_controls.append(ft.Container(
                    content=ft.Column([ft.Text("消費するペア：", color="white"), ft.Row(decision_nodes, wrap=True)]),
                    padding=15, bgcolor="#333333", border_radius=5
                ))

            elif game.turn_step == "MIMIC_SELECTION":
                mimic_nodes = []
                other_cards = list(set([c for c in display_my_hand if c != "カモフラージュ"]))
                deck_len = len(game.deck) 
                
                for target in other_cards:
                    def make_on_mimic_target(t=target):
                        def on_mimic_execute(e):
                            GameService.activate_ability(
                                game,
                                my_role,
                                t,
                                my_name,
                                mimic=True,
                            )
                            sync()
                        return on_mimic_execute
                    
                    is_target_disabled = False
                    t_display = NAME_MAP.get(target, target)
                    target_text = f"{t_display} で発動"
                    if deck_len <= 2 and target != "ヒーリング":
                        is_target_disabled = True
                        target_text += " ⚠️山札不足"
                    mimic_nodes.append(ft.Button(target_text, on_click=make_on_mimic_target(target), disabled=is_target_disabled))
                
                def on_cancel_mimic(e):
                    GameService.cancel_mimic_selection(game)
                    sync()
                mimic_nodes.append(ft.Button("キャンセル", on_click=on_cancel_mimic))
                
                new_controls.append(ft.Container(
                    content=ft.Column([ft.Text("カモフラージュ２枚と一緒に捨てる手札：", color="white"), ft.Row(mimic_nodes, wrap=True)]),
                    padding=15, bgcolor="#442222", border_radius=5
                ))

            elif game.turn_step == "TELEPORT_SELECTION":
                tel_nodes = []
                for t_name in game.types:
                    def make_tel_click(target_name=t_name):
                        def on_tel_click(e):
                            GameService.teleport(
                                game,
                                my_role,
                                target_name,
                                my_name,
                            )
                            sync()
                        return on_tel_click
                    tel_nodes.append(ft.Button(t_name, on_click=make_tel_click(t_name)))

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【テレポート(瞬間移動)】相手の手札から消し去るカードを宣言してください：", color="white", weight="bold"),
                        ft.Row(tel_nodes, wrap=True)
                    ]), padding=15, bgcolor="#332244", border_radius=5
                ))

            elif game.turn_step == "PSY_DISCARD_SELECTION":
                discard_nodes = []
                for idx, c in enumerate(display_op_hand):
                    def make_discard_click(target_card=c):
                        def on_discard_click(e):
                            GameService.psychokinesis_discard(
                                game,
                                my_role,
                                target_card,
                                my_name,
                            )
                            sync()
                        return on_discard_click
                    discard_nodes.append(ft.Button(f"伏せカード {idx+1}", on_click=make_discard_click(c)))

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【サイコキネシス(念力) 1/2】相手の手札から捨てさせるカードを選んでください：", color="white", weight="bold"),
                        ft.Row(discard_nodes, wrap=True)
                    ]), padding=15, bgcolor="#442244", border_radius=5
                ))

            elif game.turn_step == "PSY_PUSH_SELECTION":
                psy_nodes = []
                face_down_discards = []
                op_groups = game.get_discard_groups(op_role)
                for g_idx, group in enumerate(op_groups):
                    if len(group) == 1 and not group[0]["is_face_up"]:
                        face_down_discards.append((g_idx, 0, group[0]))
                        
                for i, (g_idx, item_idx, target_item) in enumerate(face_down_discards):
                    def make_psy_click(t_g_idx=g_idx, t_name=target_item["name"], display_num=i+1):
                        def on_psy_click(e):
                            GameService.psychokinesis_push(
                                game,
                                my_role,
                                t_g_idx,
                                my_name,
                                display_number=display_num,
                            )
                            sync()
                        return on_psy_click
                    psy_nodes.append(ft.Button(f"裏向きの捨て札 {i+1}", on_click=make_psy_click(g_idx, target_item["name"], i+1)))

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【サイコキネシス(念力) 2/2】相手の手札に加える裏向きの捨て札を選んでください：", color="white", weight="bold"),
                        ft.Row(psy_nodes, wrap=True)
                    ]), padding=15, bgcolor="#224444", border_radius=5
                ))

            elif game.turn_step == "REGEN_SELECTION":
                reg_nodes = []
                for list_idx, item in enumerate(game.regen_pool):
                    is_selected = list_idx in game.temp_selection
                    def make_reg_click(target_idx=list_idx):
                        def on_reg_click(e):
                            GameService.toggle_healing_selection(
                                game,
                                target_idx,
                            )
                            sync()
                        return on_reg_click
                    
                    prefix = "自分" if item["owner"] == my_role else "相手"
                    is_mine = (my_role == item["owner"])
                    show_name = item["name"] if (item["is_face_up"] or is_mine) else "？"
                    display_text = f"【{prefix}】{show_name}" if item["is_face_up"] else f"【{prefix}】裏向き({show_name})"
                    bg_color = "orange" if is_selected else ("#E0E0E0" if item["is_face_up"] else "#555555")
                    text_color = "black" if (is_selected or item["is_face_up"]) else "white"
                    reg_nodes.append(ft.Button(display_text, on_click=make_reg_click(list_idx), bgcolor=bg_color, color=text_color))
                
                def on_confirm_reg(e):
                    GameService.confirm_healing(game, my_role, my_name)
                    sync()

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"【ヒーリング(再生)】山札に戻すカードを選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                        ft.Row(reg_nodes, wrap=True),
                        ft.Button("選択完了", on_click=on_confirm_reg, bgcolor="blue", color="white")
                    ]), padding=15, bgcolor="#224422", border_radius=5
                ))

            elif game.turn_step == "CLAIR_SELECTION":
                clair_nodes = []
                for list_idx, item in enumerate(game.clair_pool):
                    is_selected = list_idx in game.temp_selection
                    def make_clair_click(target_idx=list_idx):
                        def on_clair_click(e):
                            GameService.toggle_clairvoyance_selection(
                                game,
                                target_idx,
                            )
                            sync()
                        return on_clair_click
                    bg_color = "orange" if is_selected else "#555555"
                    text_color = "black" if is_selected else "white"
                    clair_nodes.append(ft.Button(item["label"], on_click=make_clair_click(list_idx), bgcolor=bg_color, color=text_color))
                
                def on_confirm_clair(e):
                    GameService.confirm_clairvoyance(game)
                    sync()

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text(f"【クレヤボヤンス(千里眼)】中身を見たいカードを最大２枚まで選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                        ft.Row(clair_nodes, wrap=True),
                        ft.Button("選択完了", on_click=on_confirm_clair, bgcolor="blue", color="white")
                    ]), padding=15, bgcolor="#222266", border_radius=5
                ))

            elif game.turn_step == "CLAIR_REVEAL":
                reveal_nodes = []
                for list_idx, item in enumerate(game.clair_pool):
                    if list_idx in game.temp_selection:
                        reveal_nodes.append(ft.Button(f"【透視】{item['name']}", bgcolor="white", color="red"))
                    else:
                        reveal_nodes.append(ft.Button(item["label"], bgcolor="#555555", color="white", disabled=True))
                        
                def on_clair_done(e):
                    GameService.finish_clairvoyance(
                        game,
                        my_role,
                        my_name,
                    )
                    sync()

                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【クレヤボヤンス(千里眼)】透視結果です。確認したら完了ボタンを押してください。", color="white", weight="bold"),
                        ft.Row(reveal_nodes, wrap=True),
                        ft.Button("確認完了", on_click=on_clair_done, bgcolor="blue", color="white")
                    ]), padding=15, bgcolor="#222266", border_radius=5
                ))

            elif game.turn_step == "PRESCIENCE_SELECT_1":
                nodes = []
                for idx, c in enumerate(game.prescience_cards):
                    def make_click(target_idx=idx, card_name=c):
                        def on_click(e):
                            GameService.choose_prescience_card(
                                game,
                                my_role,
                                target_idx,
                                my_name,
                            )
                            sync()
                        return on_click
                    nodes.append(ft.Button(c, on_click=make_click(idx)))
                
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【プリサイエンス(未来予知) 1/3】山札の一番上にするカードを選んでください：", color="white", weight="bold"),
                        ft.Row(nodes, wrap=True)
                    ]), padding=15, bgcolor="#666622", border_radius=5
                ))

            elif game.turn_step == "PRESCIENCE_SELECT_2":
                nodes = []
                for idx, c in enumerate(game.prescience_cards):
                    def make_click(target_idx=idx, card_name=c):
                        def on_click(e):
                            GameService.choose_prescience_card(
                                game,
                                my_role,
                                target_idx,
                                my_name,
                            )
                            sync()
                        return on_click
                    nodes.append(ft.Button(c, on_click=make_click(idx)))
                    
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【プリサイエンス(未来予知) 2/3】山札の上から2番目にするカードを選んでください（残りが3番目）：", color="white", weight="bold"),
                        ft.Row(nodes, wrap=True)
                    ]), padding=15, bgcolor="#666622", border_radius=5
                ))

        chat_messages = ft.ListView(height=150, spacing=2, auto_scroll=True)
        for c_msg in getattr(game, "chat_history", []):
            chat_messages.controls.append(ft.Text(c_msg, color="white", size=14))
            
        chat_input = ft.TextField(hint_text="チャットを入力してEnter...", expand=True, bgcolor="#444444", color="white")
        
        def on_chat_send(e):
            if not GameService.send_chat(game, my_name, chat_input.value):
                return
            chat_input.value = ""
            sync()
            
        chat_input.on_submit = on_chat_send
        chat_send_btn = ft.Button("送信", on_click=on_chat_send, bgcolor="green", color="white")
        
        new_controls.append(
            ft.Container(
                content=ft.Column([
                    ft.Divider(color="grey"), ft.Text("--- チャット ---", color="grey", weight="bold"),
                    chat_messages, ft.Row([chat_input, chat_send_btn])
                ]), padding=10, bgcolor="#222222", border_radius=5
            )
        )

        if getattr(game, "turn_step", "") in ["GAME_CLEAR", "GAME_OVER"]:
            rematch_requests = getattr(game, "rematch_requests", set())
            
            if my_role in rematch_requests:
                new_controls.insert(-1, ft.Text("⏳ 相手の再戦承認を待っています...", color="cyan", weight="bold"))
            elif len(rematch_requests) > 0:
                new_controls.insert(-1, ft.Text("🔔 相手が「もう一度対戦する」を希望しています！", color="orange", weight="bold"))
                
            if my_role not in rematch_requests:
                def on_rematch_click(e):
                    RoomService.request_rematch(game, my_role)
                    sync()
                    
                def on_leave_click(e):
                    RoomService.disband_room(
                        GAME_ROOMS,
                        user_data["room_id"],
                        game,
                    )
                    sync()
                    page.pubsub.unsubscribe_topic(user_data["room_id"])
                    show_title_screen(page, user_data, GAME_ROOMS, go_to_game)
                    
                new_controls.insert(-1, ft.Row([
                    ft.Button("もう一度対戦する 🔄", on_click=on_rematch_click, bgcolor="blue", color="white", height=50),
                    ft.Button("部屋を退出する 🚪", on_click=on_leave_click, bgcolor="red", color="white", height=50)
                ]))

        page.controls.clear()
        page.controls.extend(new_controls)
        page.update()

    refresh()