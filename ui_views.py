"""タイトル画面・ゲーム画面・各カード能力の操作UIを組み立てるモジュール。"""

import flet as ft
import random
from collections import Counter
import threading
import time
from game_logic import EsperGame

NAME_MAP = {
    "クレヤボヤンス": "クレヤボヤンス(千里眼)",
    "タイムリープ": "タイムリープ(時間移動)",
    "サイコキネシス": "サイコキネシス(念力)",
    "プリサイエンス": "プリサイエンス(未来予知)",
    "テレポート": "テレポート(瞬間移動)",
    "ヒーリング": "ヒーリング(再生)",
    "カモフラージュ": "カモフラージュ(擬態)"
}

def show_title_screen(page: ft.Page, user_data: dict, GAME_ROOMS: dict, go_to_game):
    page.controls.clear()
    
    title_text = ft.Text("🌟 超能力カードゲーム ESPER 🌐", size=32, weight="bold", color="orange")
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
        
        if user_data["room_id"] not in GAME_ROOMS:
            GAME_ROOMS[user_data["room_id"]] = EsperGame()
        
        game = GAME_ROOMS[user_data["room_id"]]
        
        if len(game.players) == 0:
            user_data["role"] = "p1"
            game.players.append(user_data["name"])
        elif len(game.players) == 1:
            user_data["role"] = "p2"
            game.players.append(user_data["name"])
            
            game.turn_step = "DECIDING_TURN"
            game.timer_started = False
        else:
            room_input.error_text = "その部屋はすでに満員です！"
            page.update()
            return
        
        go_to_game()

    # CPU戦の難易度別スタート処理
    def start_cpu_game(level, name_suffix):
        user_data["name"] = name_input.value
        user_data["room_id"] = f"cpu_room_{int(time.time())}"
        user_data["has_left"] = False
        
        GAME_ROOMS[user_data["room_id"]] = EsperGame()
        game = GAME_ROOMS[user_data["room_id"]]
        game.is_cpu = True
        game.cpu_level = level
        
        user_data["role"] = "p1"
        game.players.append(user_data["name"])
        game.players.append(f"CPU（{name_suffix}）")
        
        game.turn_step = "DECIDING_TURN"
        game.timer_started = False
        go_to_game()

    def on_cpu_easy(e): start_cpu_game("easy", "初級")
    def on_cpu_normal(e): start_cpu_game("normal", "中級")
    def on_cpu_hard(e): start_cpu_game("hard", "上級")

    join_btn = ft.Button("このあいことばで対戦部屋に入る 🚀", on_click=on_join_click, bgcolor="green", color="white", width=300, height=50)
    cpu_easy_btn = ft.Button("1人プレイ（vs CPU 初級） 🔰", on_click=on_cpu_easy, bgcolor="cyan", color="black", width=300)
    cpu_normal_btn = ft.Button("1人プレイ（vs CPU 中級） 🤖", on_click=on_cpu_normal, bgcolor="blue", color="white", width=300)
    cpu_hard_btn = ft.Button("1人プレイ（vs CPU 上級） 👹", on_click=on_cpu_hard, bgcolor="purple", color="white", width=300)
    
    page.add(
        ft.Row([
            ft.Column([
                ft.Container(height=50), title_text, ft.Container(height=20),
                name_input, 
                ft.Divider(color="grey"),
                room_input, join_btn,
                ft.Divider(color="grey"),
                cpu_easy_btn, cpu_normal_btn, cpu_hard_btn
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        ], alignment=ft.MainAxisAlignment.CENTER)
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

    cpu_active_steps = [
        "DISCARD", "DRAW", "THINK", "ABILITY", "TELEPORT_SELECTION",
        "PSY_DISCARD_SELECTION", "PSY_PUSH_SELECTION", "REGEN_SELECTION",
        "CLAIR_SELECTION", "CLAIR_REVEAL", "PRESCIENCE_SELECT_1", "PRESCIENCE_SELECT_2"
    ]
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
            title=ft.Text(f"📜 最新ログ: {latest_text}", color="white", weight="bold", no_wrap=True),
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
                        padding=4, # ←★エラーの原因だった `ft.padding.symmetric` を削除し、安全な数値に修正しました
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
                ft.Text("【ゲーム外】最初に除外された3枚:", color="yellow", weight="bold"),
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
            page.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("対戦が終了し、部屋が解散されました。", color="red", size=20, weight="bold"),
                        ft.Container(height=20),
                        ft.Button("タイトル画面に戻る", on_click=on_return_title, bgcolor="blue", color="white", width=300, height=50)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=50, alignment=ft.Alignment.CENTER
                )
            )
            page.update()
            return

        # ==========================================
        # CPUの自動行動ロジック（難易度別）
        # ==========================================
        if getattr(game, "is_cpu", False) and game.current_turn == "p2" and game.turn_step in cpu_active_steps:
            if not getattr(game, "cpu_acting", False):
                game.cpu_acting = True
                def run_cpu():
                    time.sleep(1.0) 
                    cpu_lvl = getattr(game, "cpu_level", "normal")

                    if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"] and game.check_esper(game.p2_hand):
                        game.add_log("p2", f"🎉【決着】CPU が「エスパー！」を宣言しました！")
                        game.turn_step = "GAME_CLEAR"
                        game.cpu_acting = False
                        sync()
                        return

                    if game.turn_step == "DISCARD":
                        card = random.choice(game.p2_hand)
                        game.p2_hand.remove(card)
                        face_down_count = sum(1 for g in game.p2_discard_groups for c in g if not c["is_face_up"])
                        game.p2_discard_groups.append([{"name": card, "is_face_up": (face_down_count >= 5), "owner": "p2"}])
                        game.add_log("p2", f"CPUがカードを１枚捨てました。")
                        game.turn_step = "DRAW"

                    elif game.turn_step == "DRAW":
                        game.fill_hand_to_6("p2")
                        game.add_log("p2", f"CPUが手札を補充しました。")
                        game.turn_step = "THINK"

                    elif game.turn_step == "THINK":
                        if cpu_lvl == "easy":
                            game.end_action("p2", "CPUはターンを終了しました。")
                        else:
                            counts = Counter(game.p2_hand)
                            deck_len = len(game.deck)
                            usable = []
                            for c, cnt in counts.items():
                                if cnt >= 2 and c != "カモフラージュ":
                                    if deck_len <= 1 and c != "ヒーリング": continue
                                    usable.append(c)
                                    
                            # 難易度による能力発動確率
                            chance = 0.7 if cpu_lvl == "normal" else 0.95
                            if usable and random.random() < chance:
                                game.turn_step = "ABILITY"
                            else:
                                game.end_action("p2", "CPUはターンを終了しました。")

                    elif game.turn_step == "ABILITY":
                        counts = Counter(game.p2_hand)
                        usable = [c for c, cnt in counts.items() if cnt >= 2 and c != "カモフラージュ"]
                        if usable:
                            ab = random.choice(usable)
                            game.p2_hand.remove(ab)
                            game.p2_hand.remove(ab)
                            game.p2_discard_groups.append([{"name": ab, "is_face_up": True, "owner": "p2"}, {"name": ab, "is_face_up": True, "owner": "p2"}])
                            
                            ability_display = NAME_MAP.get(ab, ab)
                            if ab == "テレポート":
                                game.turn_step = "TELEPORT_SELECTION"
                            elif ab == "サイコキネシス":
                                if game.p1_hand:
                                    game.turn_step = "PSY_DISCARD_SELECTION"
                                    game.log_message = f"CPUが「{ability_display}」を発動！"
                                else:
                                    game.end_action("p2", f"CPUが「{ability_display}」を発動！しかし相手の手札は空だった")
                            elif ab == "ヒーリング":
                                flat_p1 = game.get_flat_discard("p1")
                                flat_p2 = game.get_flat_discard("p2")
                                if not flat_p1 and not flat_p2:
                                    game.end_action("p2", f"CPUが「{ability_display}」を発動！しかし捨て札がなかった")
                                else:
                                    game.turn_step = "REGEN_SELECTION"
                                    game.temp_selection = []
                                    game.regen_pool = []
                                    for g_idx, group in enumerate(game.p1_discard_groups):
                                        for item_idx, c in enumerate(group):
                                            game.regen_pool.append({"owner": "p1", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                                    for g_idx, group in enumerate(game.p2_discard_groups):
                                        for item_idx, c in enumerate(group):
                                            game.regen_pool.append({"owner": "p2", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                                    game.log_message = f"CPUが「{ability_display}」を発動！"
                            elif ab == "クレヤボヤンス":
                                game.turn_step = "CLAIR_SELECTION"
                                game.temp_selection = []
                                game.clair_pool = []
                                for idx, c in enumerate(game.p1_hand):
                                    game.clair_pool.append({"type": "hand", "idx": idx, "name": c, "label": f"あなたの伏せ手札"})
                                for g_idx, group in enumerate(game.p1_discard_groups):
                                    if not group[0]["is_face_up"]:
                                        game.clair_pool.append({"type": "discard", "g_idx": g_idx, "name": group[0]["name"], "label": f"あなたの裏向き捨て札"})
                                if not game.clair_pool:
                                    game.end_action("p2", f"CPUが「{ability_display}」を発動！しかし対象になるカードがなかった")
                                else:
                                    game.log_message = f"CPUが「{ability_display}」を発動！"
                            elif ab == "プリサイエンス":
                                count = min(3, len(game.deck))
                                if count == 0:
                                    game.end_action("p2", f"CPUが「{ability_display}」を発動！しかし山札が空だった")
                                else:
                                    game.prescience_cards = [game.deck.pop() for _ in range(count)]
                                    game.prescience_ordered = []
                                    game.turn_step = "PRESCIENCE_SELECT_1"
                            elif ab == "タイムリープ":
                                game.extra_turn = True
                                game.fill_hand_to_6("p2")
                                game.end_action("p2", f"CPUが「{ability_display}」を発動！追加ターンを得た")

                    elif game.turn_step == "TELEPORT_SELECTION":
                        target_name = random.choice(game.types)
                        removed_count = game.p1_hand.count(target_name)
                        my_needs = 6 - len(game.p2_hand)
                        op_needs = 6 - (len(game.p1_hand) - removed_count)
                        
                        if (my_needs + op_needs) > len(game.deck):
                            game.trigger_draw(f"補充に必要な山札が足りなくなりました")
                        else:
                            for _ in range(removed_count):
                                game.p1_hand.remove(target_name)
                            if removed_count > 0:
                                game.p1_discard_groups.append([{"name": target_name, "is_face_up": True, "owner": "p1"} for _ in range(removed_count)])
                            for _ in range(op_needs):
                                if game.deck: game.p1_hand.append(game.deck.pop())
                            game.fill_hand_to_6("p2")
                            
                            t_display = NAME_MAP.get(target_name, target_name)
                            game.end_action("p2", f"CPUが「テレポート(瞬間移動)」発動！【{t_display}】を宣言し、あなたから {removed_count} 枚捨てさせた！")

                    elif game.turn_step == "PSY_DISCARD_SELECTION":
                        target_card = random.choice(game.p1_hand)
                        game.p1_hand.remove(target_card)
                        game.p1_discard_groups.append([{"name": target_card, "is_face_up": True, "owner": "p1"}])
                        
                        face_down_discards = [item for group in game.p1_discard_groups if len(group) == 1 for item in group if not item["is_face_up"]]
                        if not face_down_discards:
                            game.p1_discard_groups.pop() 
                            game.p1_hand.append(target_card)
                            game.fill_hand_to_6("p2")
                            game.end_action("p2", f"CPUが「サイコキネシス(念力)」発動！しかし戻せる裏向きカードがないため手札に戻った")
                        else:
                            game.turn_step = "PSY_PUSH_SELECTION"

                    elif game.turn_step == "PSY_PUSH_SELECTION":
                        face_down_discards = []
                        for g_idx, group in enumerate(game.p1_discard_groups):
                            if len(group) == 1 and not group[0]["is_face_up"]:
                                face_down_discards.append((g_idx, group[0]["name"]))
                        
                        t_g_idx, t_name = random.choice(face_down_discards)
                        game.p1_discard_groups.pop(t_g_idx)
                        game.p1_hand.append(t_name)
                        game.fill_hand_to_6("p2")
                        game.end_action("p2", f"CPUが「サイコキネシス(念力)」であなたに裏向きのカードを押し付けた！")

                    elif game.turn_step == "REGEN_SELECTION":
                        count = min(3, len(game.regen_pool))
                        selected_indices = random.sample(range(len(game.regen_pool)), count)
                        selected_items = [game.regen_pool[i] for i in selected_indices]
                        
                        def get_sort_key(item): return (item["g_idx"], item["item_idx"])
                        p1_items = sorted([item for item in selected_items if item["owner"] == "p1"], key=get_sort_key, reverse=True)
                        p2_items = sorted([item for item in selected_items if item["owner"] == "p2"], key=get_sort_key, reverse=True)
                        
                        for item in p1_items:
                            game.deck.append(game.p1_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                            if not game.p1_discard_groups[item["g_idx"]]: game.p1_discard_groups.pop(item["g_idx"])
                        for item in p2_items:
                            game.deck.append(game.p2_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                            if not game.p2_discard_groups[item["g_idx"]]: game.p2_discard_groups.pop(item["g_idx"])
                        
                        random.shuffle(game.deck)
                        game.fill_hand_to_6("p2")
                        game.end_action("p2", f"CPUが「ヒーリング(再生)」で {count} 枚のカードを山札に戻した！")

                    elif game.turn_step == "CLAIR_SELECTION":
                        count = min(2, len(game.clair_pool))
                        game.temp_selection = random.sample(range(len(game.clair_pool)), count)
                        game.turn_step = "CLAIR_REVEAL"

                    elif game.turn_step == "CLAIR_REVEAL":
                        game.temp_selection = []
                        game.fill_hand_to_6("p2")
                        game.end_action("p2", f"CPUが「クレヤボヤンス(千里眼)」であなたのカードを透視した！")

                    elif game.turn_step == "PRESCIENCE_SELECT_1":
                        c = random.choice(game.prescience_cards)
                        game.prescience_ordered.append(c)
                        game.prescience_cards.remove(c)
                        if len(game.prescience_ordered) < 2 and game.prescience_cards:
                            game.turn_step = "PRESCIENCE_SELECT_2"
                        else:
                            game.p2_hand.extend(game.prescience_ordered)
                            game.fill_hand_to_6("p2")
                            game.deck.extend(game.prescience_cards)
                            game.prescience_ordered = []
                            game.prescience_cards = []
                            game.end_action("p2", f"CPUが「プリサイエンス(未来予知)」を発動し、未来を覗き見た！")

                    elif game.turn_step == "PRESCIENCE_SELECT_2":
                        c = random.choice(game.prescience_cards)
                        game.prescience_ordered.append(c)
                        game.prescience_cards.remove(c)
                        game.p2_hand.extend(game.prescience_ordered)
                        game.fill_hand_to_6("p2")
                        game.deck.extend(game.prescience_cards)
                        game.prescience_ordered = []
                        game.prescience_cards = []
                        game.end_action("p2", f"CPUが「プリサイエンス(未来予知)」を発動し、未来を覗き見た！")

                    game.cpu_acting = False
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
                game.current_turn = random.choice(["p1", "p2"])
                game.turn_step = "DISCARD"
                first_player_name = game.get_player_name(game.current_turn)
                game.add_log(None, f"🎉 抽選結果：【{first_player_name}】の先攻でスタート！")
                sync()

            if my_role == "p1" and not getattr(game, "timer_started", False):
                game.timer_started = True
                threading.Thread(target=execute_roulette).start()

            new_controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.ProgressRing(color="orange"),
                        ft.Text("🎲 先攻・後攻 コイントス抽選中...", color="orange", size=24, weight="bold")
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=50, alignment=ft.Alignment.CENTER
                )
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
            
            if getattr(game, "is_cpu", False):
                game.rematch_requests.add("p2")
            
        is_my_turn = (game.current_turn == my_role)
        
        if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"] and game.check_esper(display_my_hand):
            def on_esper_declare(e):
                game.add_log(my_role, f"🎉【決着】{my_name} が「エスパー！」を宣言しました！")
                game.turn_step = "GAME_CLEAR"
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
            def route_ability(ability_name):
                ability_display = NAME_MAP.get(ability_name, ability_name)

                if ability_name == "テレポート":
                    game.turn_step = "TELEPORT_SELECTION"
                elif ability_name == "サイコキネシス":
                    if true_op_hand:
                        game.turn_step = "PSY_DISCARD_SELECTION"
                        game.log_message = f"「{ability_display}」発動！捨てる相手の伏せカードを選んでください。"
                    else:
                        game.end_action(my_role, f"「{ability_display}」発動！しかし相手の手札は空だった")
                elif ability_name == "ヒーリング":
                    flat_p1 = game.get_flat_discard("p1")
                    flat_p2 = game.get_flat_discard("p2")
                    if not flat_p1 and not flat_p2:
                        game.end_action(my_role, f"「{ability_display}」発動！しかし捨て札がなかった")
                    else:
                        game.turn_step = "REGEN_SELECTION"
                        game.temp_selection = []
                        game.regen_pool = []
                        for g_idx, group in enumerate(game.get_discard_groups("p1")):
                            for item_idx, c in enumerate(group):
                                game.regen_pool.append({"owner": "p1", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                        for g_idx, group in enumerate(game.get_discard_groups("p2")):
                            for item_idx, c in enumerate(group):
                                game.regen_pool.append({"owner": "p2", "g_idx": g_idx, "item_idx": item_idx, "name": c["name"], "is_face_up": c["is_face_up"]})
                        game.log_message = f"「{ability_display}」発動！山札に戻すカードを選んでください。"
                elif ability_name == "クレヤボヤンス":
                    game.turn_step = "CLAIR_SELECTION"
                    game.temp_selection = []
                    game.clair_pool = []
                    for idx, c in enumerate(display_op_hand):
                        game.clair_pool.append({"type": "hand", "idx": idx, "name": c, "label": f"相手の伏せ手札 {idx+1}"})
                    for g_idx, group in enumerate(game.get_discard_groups(op_role)):
                        if not group[0]["is_face_up"]:
                            game.clair_pool.append({"type": "discard", "g_idx": g_idx, "name": group[0]["name"], "label": f"相手の裏向き捨て札 {g_idx+1}"})
                    
                    if not game.clair_pool:
                        game.end_action(my_role, f"「{ability_display}」発動！しかし対象になるカードがなかった")
                    else:
                        game.log_message = f"「{ability_display}」発動！透視するカードを選んでください。"
                elif ability_name == "プリサイエンス":
                    count = min(3, len(game.deck))
                    if count == 0:
                        game.end_action(my_role, f"「{ability_display}」発動！しかし山札が空だった")
                    else:
                        game.prescience_cards = [game.deck.pop() for _ in range(count)]
                        game.prescience_ordered = []
                        game.turn_step = "PRESCIENCE_SELECT_1"
                        game.log_message = f"「{ability_display}」発動！一番上に配置するカードを選んでください。"
                elif ability_name == "タイムリープ":
                    game.extra_turn = True
                    game.fill_hand_to_6(my_role)
                    game.end_action(my_role, f"「{ability_display}」発動！{my_name} は追加ターンを得た")

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
                        true_hand = game.get_hand(my_role)
                        true_hand.remove(target_card)
                        
                        my_discard_groups = game.get_discard_groups(my_role)
                        face_down_count = sum(1 for g in my_discard_groups for c in g if not c["is_face_up"])
                        is_face_up = face_down_count >= 5
                        
                        my_discard_groups.append([{"name": target_card, "is_face_up": is_face_up, "owner": my_role}])
                        
                        game.log_message = f"{my_name} がカードを１枚捨てました。山札から補充してください。"
                        game.turn_step = "DRAW"
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
                    game.fill_hand_to_6(my_role)
                    game.turn_step = "THINK"
                    game.log_message = f"{my_name} が手札を補充しました。能力を使いますか？"
                    sync()
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【補充】山札からカードを１枚引いてください", color="white", weight="bold"),
                        ft.Button("山札から引く", on_click=on_draw, bgcolor="blue", color="white")
                    ]), padding=15, bgcolor="#224422", border_radius=5
                ))

            elif game.turn_step == "THINK":
                def on_go_ability(e):
                    game.turn_step = "ABILITY"
                    sync()
                def on_pass(e):
                    game.end_action(my_role, f"{my_name} は能力を使わずにターンを終了した")
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
                    game.turn_step = "THINK"
                    sync()
                decision_nodes.append(ft.Button("戻る", on_click=on_cancel))
                
                for ability in usable_abilities:
                    def make_on_click(ab=ability):
                        def on_ability_click(e):
                            true_hand = game.get_hand(my_role)
                            true_hand.remove(ab)
                            true_hand.remove(ab)
                            group = [{"name": ab, "is_face_up": True, "owner": my_role}, {"name": ab, "is_face_up": True, "owner": my_role}]
                            game.get_discard_groups(my_role).append(group)
                            route_ability(ab)
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
                            game.turn_step = "MIMIC_SELECTION"
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
                            true_hand = game.get_hand(my_role)
                            true_hand.remove("カモフラージュ")
                            true_hand.remove("カモフラージュ")
                            true_hand.remove(t)
                            group = [{"name": "カモフラージュ", "is_face_up": True, "owner": my_role}, {"name": "カモフラージュ", "is_face_up": True, "owner": my_role}, {"name": t, "is_face_up": True, "owner": my_role}]
                            game.get_discard_groups(my_role).append(group)
                            route_ability(t)
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
                    game.turn_step = "ABILITY"
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
                            removed_count = true_op_hand.count(target_name)
                            my_needs = 6 - len(display_my_hand)
                            op_needs = 6 - (len(true_op_hand) - removed_count)
                            
                            if (my_needs + op_needs) > len(game.deck):
                                game.trigger_draw(f"補充に必要な山札が足りなくなりました")
                                sync()
                                return
                                
                            for _ in range(removed_count):
                                true_op_hand.remove(target_name)
                            
                            if removed_count > 0:
                                group = [{"name": target_name, "is_face_up": True, "owner": op_role} for _ in range(removed_count)]
                                game.get_discard_groups(op_role).append(group)
                                
                            for _ in range(op_needs):
                                if game.deck: true_op_hand.append(game.deck.pop())
                            game.fill_hand_to_6(my_role)
                            
                            t_display = NAME_MAP.get(target_name, target_name)
                            game.end_action(my_role, f"「テレポート(瞬間移動)」発動！【{t_display}】を宣言し、相手から {removed_count} 枚捨てさせた！")
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
                            true_op_hand.remove(target_card)
                            
                            op_groups = game.get_discard_groups(op_role)
                            op_groups.append([{"name": target_card, "is_face_up": True, "owner": op_role}])
                            
                            face_down_discards = [item for group in op_groups if len(group) == 1 for item in group if not item["is_face_up"]]
                            
                            if not face_down_discards:
                                op_groups.pop() 
                                true_op_hand.append(target_card)
                                game.fill_hand_to_6(my_role)
                                game.end_action(my_role, f"「サイコキネシス(念力)」発動！しかし相手の場に戻せる裏向きカードがないため手札に戻った")
                            else:
                                game.log_message = f"「サイコキネシス(念力)」発動！続けて押し付けるカードを選択中..."
                                game.turn_step = "PSY_PUSH_SELECTION"
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
                            op_groups.pop(t_g_idx)
                            true_op_hand.append(t_name)
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role, f"{my_name} は続けて、相手に 裏向きの捨て札 {display_num} を押し付けた！")
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
                            if target_idx in game.temp_selection: game.temp_selection.remove(target_idx)
                            elif len(game.temp_selection) < 3: game.temp_selection.append(target_idx)
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
                    selected_items = [game.regen_pool[i] for i in game.temp_selection]
                    returned_info = []
                    for item in selected_items:
                        owner_str = "自分" if item["owner"] == my_role else "相手"
                        if item["is_face_up"]: returned_info.append(f"【{owner_str}】の表向き({item['name']})")
                        else: returned_info.append(f"【{owner_str}】の裏向きカード")
                    joined_info = "、".join(returned_info)
                    
                    def get_sort_key(item): return (item["g_idx"], item["item_idx"])
                    p1_items = sorted([item for item in selected_items if item["owner"] == "p1"], key=get_sort_key, reverse=True)
                    p2_items = sorted([item for item in selected_items if item["owner"] == "p2"], key=get_sort_key, reverse=True)
                    
                    for item in p1_items:
                        game.deck.append(game.p1_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                        if not game.p1_discard_groups[item["g_idx"]]: game.p1_discard_groups.pop(item["g_idx"])
                    for item in p2_items:
                        game.deck.append(game.p2_discard_groups[item["g_idx"]].pop(item["item_idx"])["name"])
                        if not game.p2_discard_groups[item["g_idx"]]: game.p2_discard_groups.pop(item["g_idx"])
                    
                    random.shuffle(game.deck)
                    game.fill_hand_to_6(my_role)
                    
                    if joined_info: game.end_action(my_role, f"「ヒーリング(再生)」発動！捨て札から {joined_info} を戻した")
                    else: game.end_action(my_role, f"「ヒーリング(再生)」発動！しかし何も戻さなかった")
                    game.temp_selection = []
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
                            if target_idx in game.temp_selection: game.temp_selection.remove(target_idx)
                            elif len(game.temp_selection) < 2: game.temp_selection.append(target_idx)
                            sync()
                        return on_clair_click
                    bg_color = "orange" if is_selected else "#555555"
                    text_color = "black" if is_selected else "white"
                    clair_nodes.append(ft.Button(item["label"], on_click=make_clair_click(list_idx), bgcolor=bg_color, color=text_color))
                
                def on_confirm_clair(e):
                    game.turn_step = "CLAIR_REVEAL"
                    game.log_message = f"「クレヤボヤンス(千里眼)」発動！透視結果を確認中..."
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
                    looked_cards = " と ".join([game.clair_pool[idx]["label"] for idx in sorted(game.temp_selection)])
                    game.temp_selection = []
                    game.fill_hand_to_6(my_role)
                    game.end_action(my_role, f"「クレヤボヤンス(千里眼)」発動！{my_name} は {looked_cards} を透視した！")
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
                            game.prescience_ordered.append(card_name)
                            game.prescience_cards.pop(target_idx)
                            if len(game.prescience_ordered) < 2 and game.prescience_cards:
                                game.turn_step = "PRESCIENCE_SELECT_2"
                            else:
                                true_hand = game.get_hand(my_role)
                                true_hand.extend(game.prescience_ordered)
                                game.fill_hand_to_6(my_role)
                                for card in game.prescience_cards:
                                    game.deck.append(card)
                                game.prescience_ordered = []
                                game.prescience_cards = []
                                game.end_action(my_role, f"「プリサイエンス(未来予知)」発動！{my_name} は未来を覗き見た！")
                            sync()
                        return on_click
                    nodes.append(ft.Button(c, on_click=make_click(idx)))
                
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【プリサイエンス(未来予知) 1/2】一番上（次に引くカード）を選んでください：", color="white", weight="bold"),
                        ft.Row(nodes, wrap=True)
                    ]), padding=15, bgcolor="#666622", border_radius=5
                ))

            elif game.turn_step == "PRESCIENCE_SELECT_2":
                nodes = []
                for idx, c in enumerate(game.prescience_cards):
                    def make_click(target_idx=idx, card_name=c):
                        def on_click(e):
                            game.prescience_ordered.append(card_name)
                            game.prescience_cards.pop(target_idx)
                            
                            true_hand = game.get_hand(my_role)
                            true_hand.extend(game.prescience_ordered)
                            game.fill_hand_to_6(my_role)
                            for card in game.prescience_cards:
                                game.deck.append(card)
                                
                            game.prescience_ordered = []
                            game.prescience_cards = []
                            game.end_action(my_role, f"「プリサイエンス(未来予知)」発動！{my_name} は未来を覗き見た！")
                            sync()
                        return on_click
                    nodes.append(ft.Button(c, on_click=make_click(idx)))
                    
                new_controls.append(ft.Container(
                    content=ft.Column([
                        ft.Text("【プリサイエンス(未来予知) 2/2】山札の２枚目にしたいカードを選んでください：", color="white", weight="bold"),
                        ft.Row(nodes, wrap=True)
                    ]), padding=15, bgcolor="#666622", border_radius=5
                ))

        chat_messages = ft.ListView(height=150, spacing=2, auto_scroll=True)
        for c_msg in getattr(game, "chat_history", []):
            chat_messages.controls.append(ft.Text(c_msg, color="white", size=14))
            
        chat_input = ft.TextField(hint_text="チャットを入力してEnter...", expand=True, bgcolor="#444444", color="white")
        
        def on_chat_send(e):
            if chat_input.value.strip() == "": return
            game.chat_history.append(f"💬 {my_name}: {chat_input.value}")
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
                    game.rematch_requests.add(my_role)
                    if len(game.rematch_requests) == 2:
                        game.reset_game()
                    sync()
                    
                def on_leave_click(e):
                    game.turn_step = "ROOM_DISBANDED"
                    sync()
                    if user_data["room_id"] in GAME_ROOMS:
                        del GAME_ROOMS[user_data["room_id"]]
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