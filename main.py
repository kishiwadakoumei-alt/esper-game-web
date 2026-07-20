import flet as ft
import random
from collections import Counter
import traceback
import os

class EsperGame:
    def __init__(self):
        self.types = ["千里眼", "時間移動", "念動力", "未来予知", "瞬間移動", "再生", "擬態"]
        self.deck = [c for c in self.types for _ in range(8)]
        random.shuffle(self.deck)
        self.deck = self.deck[3:]
        
        self.p1_hand = [self.deck.pop() for _ in range(6)]
        self.p2_hand = [self.deck.pop() for _ in range(6)]
        
        self.p1_discard_groups = []
        self.p2_discard_groups = []
        
        self.players = [] 
        
        self.temp_selection = []
        self.regen_pool = [] 
        self.prescience_cards = []
        self.prescience_ordered = []
        
        self.extra_turn = False
        self.current_turn = "p1"
        self.turn_step = "WAITING"
        self.log_message = "対戦相手の入室を待っています..."

    def sort_hand(self, hand):
        counts = Counter(hand)
        return sorted(list(hand), key=lambda x: (-counts[x], x))

    def check_esper(self, hand):
        counts = Counter(hand)
        mimic_count = counts.get("擬態", 0)
        if mimic_count >= 5: return True
        wildcard_count = mimic_count // 2 
        for card, count in counts.items():
            if card != "擬態" and count + wildcard_count >= 5:
                return True
        return False

    def get_hand(self, role): return self.p1_hand if role == "p1" else self.p2_hand
    def set_hand(self, role, val):
        if role == "p1": self.p1_hand = val
        else: self.p2_hand = val

    def get_discard_groups(self, role): return self.p1_discard_groups if role == "p1" else self.p2_discard_groups
    def get_op_role(self, role): return "p2" if role == "p1" else "p1"

    def get_flat_discard(self, role):
        groups = self.get_discard_groups(role)
        flat_list = []
        for group in groups:
            flat_list.extend(group)
        return flat_list

    def fill_hand_to_6(self, role):
        hand = self.get_hand(role)
        while len(hand) < 6 and self.deck:
            hand.append(self.deck.pop())

    def trigger_endgame(self, reason):
        self.turn_step = "GAME_OVER"
        p1_counts = Counter(self.p1_hand)
        p2_counts = Counter(self.p2_hand)
        p1_max = max(p1_counts.values()) if p1_counts else 0
        p2_max = max(p2_counts.values()) if p2_counts else 0
        
        msg = f"【終了】{reason}。"
        if p1_max > p2_max:
            self.log_message = msg + " 最大同種判定により、プレイヤー1の勝利！🎉"
        elif p2_max > p1_max:
            self.log_message = msg + " 最大同種判定により、プレイヤー2の勝利！🎉"
        else:
            self.log_message = msg + " 最大同種が同じため引き分け！⚖️"

    def trigger_draw(self, reason):
        self.turn_step = "GAME_OVER"
        self.log_message = f"⚖️【引き分け】{reason}⚖️"

    def end_action(self, current_role):
        if len(self.deck) == 0:
            self.trigger_endgame("山札が尽きました")
            return
        
        if len(self.p1_discard_groups) >= 18 or len(self.p2_discard_groups) >= 18:
            self.trigger_endgame("捨て札が18組（上限）に達しました")
            return
        
        if self.extra_turn:
            self.extra_turn = False
            self.log_message = f"⏰ タイムリープ！続けてプレイヤー{1 if current_role=='p1' else 2}の番です。"
            self.turn_step = "DISCARD"
        else:
            self.current_turn = self.get_op_role(current_role)
            self.turn_step = "DISCARD"
            self.log_message = f"プレイヤー{1 if self.current_turn=='p1' else 2}のターンです。カードを捨ててください。"

GAME_ROOMS = {}

def main(page: ft.Page):
    try:
        page.bgcolor = "#222222"
        page.scroll = "auto"
        page.title = "超能力カードゲーム ESPER"

        user_data = {"name": "ゲスト", "room_id": "", "role": ""}
        game = None

        def show_title_screen():
            page.controls.clear()
            
            title_text = ft.Text("🌟 超能力カードゲーム ESPER 🌐", size=32, weight="bold", color="orange")
            name_input = ft.TextField(label="あなたの名前", value="プレイヤー", width=300, bgcolor="#333333")
            room_input = ft.TextField(label="あいのことば（ルームID）", hint_text="友達と同じ言葉を入れてね", width=300, bgcolor="#333333")
            
            def on_join_click(e):
                if not room_input.value:
                    room_input.error_text = "合言葉を入力してください！"
                    page.update()
                    return
                
                user_data["name"] = name_input.value
                user_data["room_id"] = room_input.value
                
                if user_data["room_id"] not in GAME_ROOMS:
                    GAME_ROOMS[user_data["room_id"]] = EsperGame()
                
                nonlocal game
                game = GAME_ROOMS[user_data["room_id"]]
                
                if len(game.players) == 0:
                    user_data["role"] = "p1"
                    game.players.append(user_data["name"])
                elif len(game.players) == 1:
                    user_data["role"] = "p2"
                    game.players.append(user_data["name"])
                    game.turn_step = "DISCARD"
                    game.log_message = "対戦相手が見つかりました！プレイヤー1の先行で開始します。"
                else:
                    room_input.error_text = "その部屋はすでに満員です！"
                    page.update()
                    return
                
                show_game_screen()

            join_btn = ft.Button("この合言葉で対戦部屋に入る 🚀", on_click=on_join_click, bgcolor="green", color="white", width=300, height=50)
            
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
            page.update()

        def show_game_screen():
            page.controls.clear()
            page.update() 
            
            def on_message(topic, msg):
                refresh()
                
            page.pubsub.subscribe_topic(user_data["room_id"], on_message)

            def sync():
                page.pubsub.send_all_on_topic(user_data["room_id"], "update")

            if len(game.players) == 2 and game.turn_step == "DISCARD":
                sync()

            room_info = ft.Container(
                content=ft.Row([
                    ft.Text(f"👤 {user_data['name']} (プレイヤー{1 if user_data['role']=='p1' else 2})", color="white", weight="bold"),
                    ft.Text(f"🔑 合言葉: {user_data['room_id']}", color="orange", weight="bold"),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                padding=10, bgcolor="#333333", border_radius=5
            )

            def get_dashboard():
                def make_group_ui(group):
                    chips = []
                    for idx, card_data in enumerate(group):
                        is_mine = (user_data["role"] == card_data["owner"])
                        show_name = card_data["name"] if (card_data["is_face_up"] or is_mine) else "？"
                        
                        if card_data["is_face_up"]:
                            color, bg = "black", "#E0E0E0"
                        else:
                            color, bg = "white", "#555555"
                            
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
                    return ft.Stack(chips, width=60 + (len(group) * 5), height=50 + (len(group) * 5))

                my_groups = game.get_discard_groups(user_data["role"])
                op_groups = game.get_discard_groups(game.get_op_role(user_data["role"]))
                
                my_dis_display = ft.Row([make_group_ui(g) for g in my_groups], wrap=True)
                op_dis_display = ft.Row([make_group_ui(g) for g in op_groups], wrap=True)
                
                return ft.Container(
                    content=ft.Column([
                        ft.Text("--- 捨て札エリア (公開情報) ---", color="white", weight="bold"),
                        ft.Text(f"自分 ({len(my_groups)}組):", color="blue"), my_dis_display,
                        ft.Text(f"相手 ({len(op_groups)}組):", color="red"), op_dis_display
                    ]), padding=10, bgcolor="#111111"
                )

            def refresh():
                new_controls = []
                new_controls.append(room_info)
                
                if game.turn_step == "WAITING":
                    new_controls.append(ft.Text("対戦相手の入室を待っています... (友達にURLと合言葉を教えてね！)", color="yellow", size=20))
                    page.controls.clear()
                    page.controls.extend(new_controls)
                    page.update()
                    return

                new_controls.append(get_dashboard())
                
                game.set_hand("p1", game.sort_hand(game.p1_hand))
                game.set_hand("p2", game.sort_hand(game.p2_hand))
                
                my_role = user_data["role"]
                op_role = game.get_op_role(my_role)
                my_hand = game.get_hand(my_role)
                op_hand = game.get_hand(op_role)
                
                new_controls.append(ft.Text(f"相手の手札枚数: {len(op_hand)}枚 / 山札: {len(game.deck)}枚", color="red", weight="bold"))
                
                if game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
                    new_controls.append(ft.Text(f"ログ: {game.log_message}", color="orange", size=18, weight="bold"))
                else:
                    new_controls.append(ft.Text(f"ログ: {game.log_message}", color="green", size=16))
                    
                is_my_turn = (game.current_turn == my_role)
                
                if game.turn_step not in ["GAME_CLEAR", "GAME_OVER"] and game.check_esper(my_hand):
                    def on_esper_declare(e):
                        game.turn_step = "GAME_CLEAR"
                        game.log_message = f"🎉【決着】プレイヤー{1 if my_role=='p1' else 2}が「エスパー！」を宣言しました！🎉"
                        sync()
                    new_controls.append(
                        ft.Button("🌟 エスパー宣言！ (同種5枚達成) 🌟", on_click=on_esper_declare, bgcolor="orange", color="black", width=400, height=50)
                    )

                if not is_my_turn and game.turn_step not in ["GAME_CLEAR", "GAME_OVER"]:
                    new_controls.append(ft.Text("⏳ 相手の操作を待っています...", color="grey", size=18))
                    hand_row = ft.Row(wrap=True)
                    for card in my_hand:
                        hand_row.controls.append(ft.Button(card, disabled=True, bgcolor="#CFD8DC", color="black"))
                    new_controls.append(hand_row)
                    
                    page.controls.clear()
                    page.controls.extend(new_controls)
                    page.update()
                    return

                def route_ability(ability_name):
                    if ability_name == "瞬間移動":
                        game.turn_step = "TELEPORT_SELECTION"
                    elif ability_name == "念動力":
                        if op_hand:
                            game.turn_step = "PSY_DISCARD_SELECTION"
                            game.log_message = "「念動力」発動！捨てる相手の手札を選んでください。"
                        else:
                            game.log_message = "「念動力」発動！しかし相手の手札は空だった。"
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role)
                    elif ability_name == "再生":
                        flat_p1 = game.get_flat_discard("p1")
                        flat_p2 = game.get_flat_discard("p2")
                        if not flat_p1 and not flat_p2:
                            game.log_message = "「ヒーリング」発動！しかし捨て札がなかった。"
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role)
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
                            game.log_message = "「ヒーリング」発動！山札に戻すカードを選んでください。"
                    elif ability_name == "千里眼":
                        if not op_hand:
                            game.log_message = "「千里眼」発動！しかし相手の手札は空だった。"
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role)
                        else:
                            game.turn_step = "CLAIR_SELECTION"
                            game.temp_selection = []
                            game.log_message = "「千里眼」発動！透視する手札を選んでください。"
                    elif ability_name == "未来予知":
                        count = min(3, len(game.deck))
                        if count == 0:
                            game.log_message = "「未来予知」発動！しかし山札が空だった。"
                            game.fill_hand_to_6(my_role)
                            game.end_action(my_role)
                        else:
                            game.prescience_cards = [game.deck.pop() for _ in range(count)]
                            game.prescience_ordered = []
                            game.turn_step = "PRESCIENCE_SELECT_1"
                            game.log_message = "「未来予知」発動！一番上に配置するカードを選んでください。"
                    elif ability_name == "時間移動":
                        game.extra_turn = True
                        game.fill_hand_to_6(my_role)
                        game.end_action(my_role)

                if game.turn_step == "DISCARD":
                    new_controls.append(ft.Text("【手札】 1枚選んで捨ててください", color="yellow"))
                elif game.turn_step in ["GAME_CLEAR", "GAME_OVER"]:
                    new_controls.append(ft.Text("【手札】 (ゲーム終了)", color="grey"))
                else:
                    new_controls.append(ft.Text("【手札】 (現在は確認のみ・クリック不可)", color="grey"))

                hand_row = ft.Row(wrap=True)
                for i, card in enumerate(list(my_hand)):
                    def make_on_click(idx=i):
                        def on_click(e):
                            if game.turn_step != "DISCARD": return
                            c = my_hand.pop(idx)
                            my_discard_groups = game.get_discard_groups(my_role)
                            
                            total_discarded = sum(len(g) for g in my_discard_groups)
                            is_face_up = total_discarded >= 5
                            
                            my_discard_groups.append([{"name": c, "is_face_up": is_face_up, "owner": my_role}])
                            
                            game.fill_hand_to_6(my_role)
                            game.log_message = f"プレイヤー{1 if my_role=='p1' else 2}がカードを捨てました。"
                            game.turn_step = "THINK"
                            sync()
                        return on_click

                    bg_color = "white" if game.turn_step == "DISCARD" else "#CFD8DC"
                    hand_row.controls.append(ft.Button(card, on_click=make_on_click(i), color="black", bgcolor=bg_color))
                new_controls.append(hand_row)

                if game.turn_step == "THINK":
                    def on_go_ability(e):
                        game.turn_step = "ABILITY"
                        sync()
                    def on_pass(e):
                        game.end_action(my_role)
                        sync()

                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text("【確認】新しい手札です。能力を使いますか？", color="white", size=16),
                            ft.Row([ft.Button("能力を使う", on_click=on_go_ability), ft.Button("ターン終了", on_click=on_pass)])
                        ]), padding=15, bgcolor="#334433", border_radius=5
                    ))

                elif game.turn_step == "ABILITY":
                    decision_nodes = []
                    counts = Counter(my_hand)
                    usable_abilities = [c for c, cnt in counts.items() if cnt >= 2 and c != "擬態"]
                    deck_len = len(game.deck)
                                        
                    def on_cancel(e):
                        game.turn_step = "THINK"
                        sync()
                    decision_nodes.append(ft.Button("戻る", on_click=on_cancel))
                    
                    for ability in usable_abilities:
                        def make_on_click(ab=ability):
                            def on_ability_click(e):
                                my_hand.remove(ab)
                                my_hand.remove(ab)
                                group = [
                                    {"name": ab, "is_face_up": True, "owner": my_role},
                                    {"name": ab, "is_face_up": True, "owner": my_role}
                                ]
                                game.get_discard_groups(my_role).append(group)
                                route_ability(ab)
                                sync()
                            return on_ability_click
                        
                        is_disabled = False
                        btn_text = f"【発動】{ability} (2枚)"
                        if deck_len == 1 and ability != "再生":
                            is_disabled = True
                            btn_text += " ⚠️山札1枚のため使用不可"
                        decision_nodes.append(ft.Button(btn_text, on_click=make_on_click(ability), disabled=is_disabled))
                    
                    if counts.get("擬態", 0) >= 2:
                        other_cards = list(set([c for c in my_hand if c != "擬態"]))
                        if other_cards:
                            def on_mimic_start_click(e):
                                game.turn_step = "MIMIC_SELECTION"
                                sync()
                            is_mimic_disabled = False
                            mimic_text = "【発動】カモフラージュ (擬態2枚+1枚)"
                            if deck_len <= 2:
                                is_mimic_disabled = True
                                mimic_text += " ⚠️山札不足"
                            decision_nodes.append(ft.Button(mimic_text, on_click=on_mimic_start_click, disabled=is_mimic_disabled))
                    
                    new_controls.append(ft.Container(
                        content=ft.Column([ft.Text("消費するペア：", color="white"), ft.Row(decision_nodes, wrap=True)]),
                        padding=15, bgcolor="#333333", border_radius=5
                    ))

                elif game.turn_step == "MIMIC_SELECTION":
                    mimic_nodes = []
                    other_cards = list(set([c for c in my_hand if c != "擬態"]))
                    for target in other_cards:
                        def make_on_mimic_target(t=target):
                            def on_mimic_execute(e):
                                my_hand.remove("擬態")
                                my_hand.remove("擬態")
                                my_hand.remove(t)
                                group = [
                                    {"name": "擬態", "is_face_up": True, "owner": my_role},
                                    {"name": "擬態", "is_face_up": True, "owner": my_role},
                                    {"name": t, "is_face_up": True, "owner": my_role}
                                ]
                                game.get_discard_groups(my_role).append(group)
                                route_ability(t)
                                sync()
                            return on_mimic_execute
                        mimic_nodes.append(ft.Button(f"{target} で発動", on_click=make_on_mimic_target(target)))
                    
                    def on_cancel_mimic(e):
                        game.turn_step = "ABILITY"
                        sync()
                    mimic_nodes.append(ft.Button("キャンセル", on_click=on_cancel_mimic))
                    
                    new_controls.append(ft.Container(
                        content=ft.Column([ft.Text("擬態2枚と一緒に捨てる手札：", color="white"), ft.Row(mimic_nodes, wrap=True)]),
                        padding=15, bgcolor="#442222", border_radius=5
                    ))

                elif game.turn_step == "TELEPORT_SELECTION":
                    tel_nodes = []
                    for t_name in game.types:
                        def make_tel_click(target_name=t_name):
                            def on_tel_click(e):
                                removed = [c for c in op_hand if c == target_name]
                                
                                my_needs = 6 - len(my_hand)
                                op_needs = 6 - (len(op_hand) - len(removed))
                                
                                if (my_needs + op_needs) > len(game.deck):
                                    msg = f"お互いに合計 {my_needs + op_needs} 枚の補充が必要ですが、山札が残り{len(game.deck)}枚のため補充できなくなりました。"
                                    game.trigger_draw(msg)
                                    sync()
                                    return
                                    
                                game.set_hand(op_role, [c for c in op_hand if c != target_name])
                                
                                if removed:
                                    group = [{"name": r, "is_face_up": True, "owner": op_role} for r in removed]
                                    game.get_discard_groups(op_role).append(group)
                                    
                                for _ in range(op_needs):
                                    if game.deck: game.get_hand(op_role).append(game.deck.pop())
                                game.log_message = f"「テレポート」発動！相手の【{target_name}】を{len(removed)}枚捨てさせた！"
                                game.fill_hand_to_6(my_role)
                                game.end_action(my_role)
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
                    discard_nodes = []
                    for idx, c in enumerate(op_hand):
                        def make_discard_click(target_idx=idx, target_card=c):
                            def on_discard_click(e):
                                discarded = op_hand.pop(target_idx)
                                op_groups = game.get_discard_groups(op_role)
                                op_groups.append([{"name": discarded, "is_face_up": True, "owner": op_role}])
                                
                                face_down_discards = [item for group in op_groups for item in group if not item["is_face_up"]]
                                
                                if not face_down_discards:
                                    op_groups.pop() 
                                    op_hand.append(discarded)
                                    game.log_message = f"相手の裏向きカードがないため、捨てさせた【{discarded}】は相手の手札に戻った！"
                                    game.fill_hand_to_6(my_role)
                                    game.end_action(my_role)
                                else:
                                    game.log_message = "相手の手札からカードを捨てさせた！"
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
                    psy_nodes = []
                    
                    face_down_discards = []
                    op_groups = game.get_discard_groups(op_role)
                    for g_idx, group in enumerate(op_groups):
                        for item_idx, item in enumerate(group):
                            if not item["is_face_up"]:
                                face_down_discards.append((g_idx, item_idx, item))
                                
                    for i, (g_idx, item_idx, target_item) in enumerate(face_down_discards):
                        def make_psy_click(t_g_idx=g_idx, t_item_idx=item_idx, t_name=target_item["name"]):
                            def on_psy_click(e):
                                op_groups[t_g_idx].pop(t_item_idx)
                                if not op_groups[t_g_idx]:
                                    op_groups.pop(t_g_idx)
                                    
                                op_hand.append(t_name)
                                game.log_message += " 続けて、相手に裏向きの捨て札を押し付けた！"
                                game.fill_hand_to_6(my_role)
                                game.end_action(my_role)
                                sync()
                            return on_psy_click
                        psy_nodes.append(ft.Button(f"裏向きの捨て札 {i+1}", on_click=make_psy_click(g_idx, item_idx, target_item["name"])))

                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text("【念動力 2/2】相手の手札に加える裏向きの捨て札を選んでください：", color="white", weight="bold"),
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
                        game.log_message += f" 捨て札から{len(selected_items)}枚のカードを山札に戻してシャッフルした！"
                        game.temp_selection = []
                        game.fill_hand_to_6(my_role)
                        game.end_action(my_role)
                        sync()

                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text(f"【再生】山札に戻すカードを選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                            ft.Row(reg_nodes, wrap=True),
                            ft.Button("選択完了", on_click=on_confirm_reg, bgcolor="blue", color="white")
                        ]), padding=15, bgcolor="#224422", border_radius=5
                    ))

                elif game.turn_step == "CLAIR_SELECTION":
                    clair_nodes = []
                    for idx, c in enumerate(op_hand):
                        is_selected = idx in game.temp_selection
                        def make_clair_click(target_idx=idx):
                            def on_clair_click(e):
                                if target_idx in game.temp_selection: game.temp_selection.remove(target_idx)
                                elif len(game.temp_selection) < 2: game.temp_selection.append(target_idx)
                                sync()
                            return on_clair_click
                        bg_color = "orange" if is_selected else "#555555"
                        text_color = "black" if is_selected else "white"
                        clair_nodes.append(ft.Button(f"伏せカード {idx+1}", on_click=make_clair_click(idx), bgcolor=bg_color, color=text_color))
                    
                    def on_confirm_clair(e):
                        game.turn_step = "CLAIR_REVEAL"
                        game.log_message += " 相手のカードを透視しました！"
                        sync()

                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text(f"【千里眼】中身を見たい相手の手札を最大2枚まで選んでください (現在: {len(game.temp_selection)}枚選択中)", color="white", weight="bold"),
                            ft.Row(clair_nodes, wrap=True),
                            ft.Button("選択完了", on_click=on_confirm_clair, bgcolor="blue", color="white")
                        ]), padding=15, bgcolor="#222266", border_radius=5
                    ))

                elif game.turn_step == "CLAIR_REVEAL":
                    reveal_nodes = []
                    for idx, c in enumerate(op_hand):
                        if idx in game.temp_selection:
                            reveal_nodes.append(ft.Button(f"【透視】{c}", bgcolor="white", color="red"))
                        else:
                            reveal_nodes.append(ft.Button(f"伏せカード {idx+1}", bgcolor="#555555", color="white", disabled=True))
                            
                    def on_clair_done(e):
                        game.temp_selection = []
                        game.fill_hand_to_6(my_role)
                        game.end_action(my_role)
                        sync()

                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text("【千里眼】透視結果です。確認したら完了ボタンを押してください。", color="white", weight="bold"),
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
                                if game.prescience_cards:
                                    game.turn_step = "PRESCIENCE_SELECT_2"
                                else:
                                    game.deck.extend(game.prescience_ordered)
                                    game.fill_hand_to_6(my_role)
                                    game.end_action(my_role)
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
                    nodes = []
                    for idx, c in enumerate(game.prescience_cards):
                        def make_click(target_idx=idx, card_name=c):
                            def on_click(e):
                                game.prescience_ordered.append(card_name)
                                game.prescience_cards.pop(target_idx)
                                game.prescience_ordered.extend(game.prescience_cards)
                                game.prescience_cards = []
                                for card in reversed(game.prescience_ordered):
                                    game.deck.append(card)
                                game.fill_hand_to_6(my_role)
                                game.end_action(my_role)
                                sync()
                            return on_click
                        nodes.append(ft.Button(c, on_click=make_click(idx)))
                        
                    new_controls.append(ft.Container(
                        content=ft.Column([
                            ft.Text("【未来予知 2/2】山札の2枚目にしたいカードを選んでください：", color="white", weight="bold"),
                            ft.Row(nodes, wrap=True)
                        ]), padding=15, bgcolor="#666622", border_radius=5
                    ))

                page.controls.clear()
                page.controls.extend(new_controls)
                page.update()

            refresh()

        show_title_screen()
    except Exception as e:
        page.add(ft.Text(f"システムエラー: {e}\n{traceback.format_exc()}", color="red"))
        page.update()

port = int(os.environ.get("PORT", 8000))
ft.app(main, port=port, view=ft.AppView.WEB_BROWSER, host="0.0.0.0")