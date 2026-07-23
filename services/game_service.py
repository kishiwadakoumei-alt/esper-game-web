"""プレイヤー操作によるゲーム状態の変更を集約するサービス。"""

import random

from game_logic import EsperGame


NAME_MAP = {
    "クレヤボヤンス": "クレヤボヤンス(千里眼)",
    "タイムリープ": "タイムリープ(時間移動)",
    "サイコキネシス": "サイコキネシス(念力)",
    "プリサイエンス": "プリサイエンス(未来予知)",
    "テレポート": "テレポート(瞬間移動)",
    "ヒーリング": "ヒーリング(再生)",
    "カモフラージュ": "カモフラージュ(擬態)",
}


class GameService:
    """Fletに依存しないゲーム操作を提供する。"""

    @staticmethod
    def start_turn_timer(game: EsperGame) -> bool:
        if getattr(game, "timer_started", False):
            return False
        game.timer_started = True
        return True

    @staticmethod
    def decide_first_player(game: EsperGame) -> str:
        game.current_turn = random.choice(["p1", "p2"])
        game.turn_step = "DISCARD"
        first_player_name = game.get_player_name(game.current_turn)
        game.add_log(
            None,
            f"🎉 抽選結果：【{first_player_name}】の先攻でスタート！",
        )
        return game.current_turn

    @staticmethod
    def declare_esper(game: EsperGame, role: str, player_name: str) -> None:
        game.add_log(
            role,
            f"🎉【決着】{player_name} が「エスパー！」を宣言しました！",
        )
        game.turn_step = "GAME_CLEAR"

    @staticmethod
    def discard_card(
        game: EsperGame,
        role: str,
        card: str,
        player_name: str,
    ) -> None:
        hand = game.get_hand(role)
        hand.remove(card)

        discard_groups = game.get_discard_groups(role)
        face_down_count = sum(
            1
            for group in discard_groups
            for item in group
            if not item["is_face_up"]
        )
        discard_groups.append(
            [{
                "name": card,
                "is_face_up": face_down_count >= 5,
                "owner": role,
            }]
        )

        if GameService._is_cpu_actor(game, role):
            game.add_log(role, "CPUがカードを１枚捨てました。")
        else:
            game.log_message = (
                f"{player_name} がカードを１枚捨てました。"
                "山札から補充してください。"
            )
        game.turn_step = "DRAW"

    @staticmethod
    def draw_hand(game: EsperGame, role: str, player_name: str) -> None:
        game.fill_hand_to_6(role)
        if GameService._is_cpu_actor(game, role):
            game.add_log(role, "CPUが手札を補充しました。")
        else:
            game.log_message = (
                f"{player_name} が手札を補充しました。能力を使いますか？"
            )
        game.turn_step = "THINK"

    @staticmethod
    def open_ability_selection(game: EsperGame) -> None:
        game.turn_step = "ABILITY"

    @staticmethod
    def cancel_ability_selection(game: EsperGame) -> None:
        game.turn_step = "THINK"

    @staticmethod
    def open_mimic_selection(game: EsperGame) -> None:
        game.turn_step = "MIMIC_SELECTION"

    @staticmethod
    def cancel_mimic_selection(game: EsperGame) -> None:
        game.turn_step = "ABILITY"

    @staticmethod
    def pass_turn(
        game: EsperGame,
        role: str,
        player_name: str,
        *,
        cpu: bool = False,
    ) -> None:
        message = (
            "CPUはターンを終了しました。"
            if cpu
            else f"{player_name} は能力を使わずにターンを終了した"
        )
        game.end_action(role, message)

    @staticmethod
    def activate_ability(
        game: EsperGame,
        role: str,
        ability_name: str,
        player_name: str,
        *,
        mimic: bool = False,
    ) -> None:
        hand = game.get_hand(role)
        if mimic:
            hand.remove("カモフラージュ")
            hand.remove("カモフラージュ")
            hand.remove(ability_name)
            group = [
                {
                    "name": "カモフラージュ",
                    "is_face_up": True,
                    "owner": role,
                },
                {
                    "name": "カモフラージュ",
                    "is_face_up": True,
                    "owner": role,
                },
                {
                    "name": ability_name,
                    "is_face_up": True,
                    "owner": role,
                },
            ]
        else:
            hand.remove(ability_name)
            hand.remove(ability_name)
            group = [
                {
                    "name": ability_name,
                    "is_face_up": True,
                    "owner": role,
                },
                {
                    "name": ability_name,
                    "is_face_up": True,
                    "owner": role,
                },
            ]

        game.get_discard_groups(role).append(group)
        GameService._route_ability(
            game,
            role,
            ability_name,
            player_name,
        )

    @staticmethod
    def teleport(
        game: EsperGame,
        role: str,
        target_name: str,
        player_name: str,
    ) -> None:
        opponent_role = game.get_op_role(role)
        hand = game.get_hand(role)
        opponent_hand = game.get_hand(opponent_role)
        removed_count = opponent_hand.count(target_name)
        my_needs = 6 - len(hand)
        opponent_needs = 6 - (len(opponent_hand) - removed_count)

        if my_needs + opponent_needs > len(game.deck):
            game.trigger_draw("補充に必要な山札が足りなくなりました")
            return

        for _ in range(removed_count):
            opponent_hand.remove(target_name)

        if removed_count > 0:
            game.get_discard_groups(opponent_role).append(
                [
                    {
                        "name": target_name,
                        "is_face_up": True,
                        "owner": opponent_role,
                    }
                    for _ in range(removed_count)
                ]
            )

        for _ in range(opponent_needs):
            if game.deck:
                opponent_hand.append(game.deck.pop())
        game.fill_hand_to_6(role)

        target_display = NAME_MAP.get(target_name, target_name)
        if GameService._is_cpu_actor(game, role):
            message = (
                "CPUが「テレポート(瞬間移動)」発動！"
                f"【{target_display}】を宣言し、あなたから "
                f"{removed_count} 枚捨てさせた！"
            )
        else:
            message = (
                "「テレポート(瞬間移動)」発動！"
                f"【{target_display}】を宣言し、相手から "
                f"{removed_count} 枚捨てさせた！"
            )
        game.end_action(role, message)

    @staticmethod
    def psychokinesis_discard(
        game: EsperGame,
        role: str,
        target_card: str,
        player_name: str,
    ) -> None:
        opponent_role = game.get_op_role(role)
        opponent_hand = game.get_hand(opponent_role)
        opponent_groups = game.get_discard_groups(opponent_role)

        opponent_hand.remove(target_card)
        opponent_groups.append(
            [{
                "name": target_card,
                "is_face_up": True,
                "owner": opponent_role,
            }]
        )

        face_down_discards = [
            item
            for group in opponent_groups
            if len(group) == 1
            for item in group
            if not item["is_face_up"]
        ]
        if not face_down_discards:
            opponent_groups.pop()
            opponent_hand.append(target_card)
            game.fill_hand_to_6(role)
            if GameService._is_cpu_actor(game, role):
                message = (
                    "CPUが「サイコキネシス(念力)」を発動！"
                    "しかし戻せる裏向きカードがないため手札に戻った"
                )
            else:
                message = (
                    "「サイコキネシス(念力)」発動！"
                    "しかし相手の場に戻せる裏向きカードがないため"
                    "手札に戻った"
                )
            game.end_action(role, message)
            return

        game.log_message = (
            "「サイコキネシス(念力)」発動！"
            "続けて押し付けるカードを選択中..."
        )
        game.turn_step = "PSY_PUSH_SELECTION"

    @staticmethod
    def psychokinesis_push(
        game: EsperGame,
        role: str,
        group_index: int,
        player_name: str,
        *,
        display_number: int | None = None,
    ) -> None:
        opponent_role = game.get_op_role(role)
        opponent_groups = game.get_discard_groups(opponent_role)
        target_name = opponent_groups.pop(group_index)[0]["name"]
        game.get_hand(opponent_role).append(target_name)
        game.fill_hand_to_6(role)

        if GameService._is_cpu_actor(game, role):
            message = (
                "CPUが「サイコキネシス(念力)」で"
                "あなたに裏向きのカードを押し付けた！"
            )
        else:
            number = display_number if display_number is not None else group_index + 1
            message = (
                f"{player_name} は続けて、相手に "
                f"裏向きの捨て札 {number} を押し付けた！"
            )
        game.end_action(role, message)

    @staticmethod
    def toggle_healing_selection(game: EsperGame, target_index: int) -> None:
        if target_index in game.temp_selection:
            game.temp_selection.remove(target_index)
        elif len(game.temp_selection) < 3:
            game.temp_selection.append(target_index)

    @staticmethod
    def confirm_healing(
        game: EsperGame,
        role: str,
        player_name: str,
    ) -> None:
        selected_items = [
            game.regen_pool[index] for index in game.temp_selection
        ]
        returned_info = []
        for item in selected_items:
            owner_text = "自分" if item["owner"] == role else "相手"
            if item["is_face_up"]:
                returned_info.append(
                    f"【{owner_text}】の表向き({item['name']})"
                )
            else:
                returned_info.append(f"【{owner_text}】の裏向きカード")

        GameService._return_discard_items_to_deck(game, selected_items)
        random.shuffle(game.deck)
        game.fill_hand_to_6(role)

        if GameService._is_cpu_actor(game, role):
            message = (
                "CPUが「ヒーリング(再生)」で "
                f"{len(selected_items)} 枚のカードを山札に戻した！"
            )
        elif returned_info:
            message = (
                "「ヒーリング(再生)」発動！捨て札から "
                f"{'、'.join(returned_info)} を戻した"
            )
        else:
            message = "「ヒーリング(再生)」発動！しかし何も戻さなかった"

        game.temp_selection = []
        game.end_action(role, message)

    @staticmethod
    def toggle_clairvoyance_selection(
        game: EsperGame,
        target_index: int,
    ) -> None:
        if target_index in game.temp_selection:
            game.temp_selection.remove(target_index)
        elif len(game.temp_selection) < 2:
            game.temp_selection.append(target_index)

    @staticmethod
    def confirm_clairvoyance(game: EsperGame) -> None:
        game.turn_step = "CLAIR_REVEAL"
        game.log_message = (
            "「クレヤボヤンス(千里眼)」発動！透視結果を確認中..."
        )

    @staticmethod
    def finish_clairvoyance(
        game: EsperGame,
        role: str,
        player_name: str,
    ) -> None:
        if GameService._is_cpu_actor(game, role):
            message = (
                "CPUが「クレヤボヤンス(千里眼)」で"
                "あなたのカードを透視した！"
            )
        else:
            looked_cards = " と ".join(
                game.clair_pool[index]["label"]
                for index in sorted(game.temp_selection)
            )
            message = (
                "「クレヤボヤンス(千里眼)」発動！"
                f"{player_name} は {looked_cards} を透視した！"
            )
        game.temp_selection = []
        game.fill_hand_to_6(role)
        game.end_action(role, message)

    @staticmethod
    def choose_prescience_card(
        game: EsperGame,
        role: str,
        target_index: int,
        player_name: str,
    ) -> None:
        game.prescience_ordered.append(
            game.prescience_cards.pop(target_index)
        )
        if len(game.prescience_ordered) < 2 and game.prescience_cards:
            game.turn_step = "PRESCIENCE_SELECT_2"
            return

        GameService._finish_prescience(game, role, player_name)

    @staticmethod
    def confirm_prescience_order(
        game: EsperGame,
        role: str,
        ordered_indices: list[int],
        player_name: str,
    ) -> None:
        game.prescience_ordered = [
            game.prescience_cards[index]
            for index in ordered_indices
        ]
        game.prescience_cards = []
        GameService._finish_prescience(game, role, player_name)

    @staticmethod
    def send_chat(game: EsperGame, player_name: str, message: str) -> bool:
        if message.strip() == "":
            return False
        game.chat_history.append(f"💬 {player_name}: {message}")
        return True

    @staticmethod
    def _route_ability(
        game: EsperGame,
        role: str,
        ability_name: str,
        player_name: str,
    ) -> None:
        ability_display = NAME_MAP.get(ability_name, ability_name)
        opponent_role = game.get_op_role(role)
        opponent_hand = game.get_hand(opponent_role)
        is_cpu = GameService._is_cpu_actor(game, role)

        if ability_name == "テレポート":
            game.turn_step = "TELEPORT_SELECTION"
            return

        if ability_name == "サイコキネシス":
            start_message = (
                f"CPUが「{ability_display}」を発動！"
                if is_cpu
                else f"「{ability_display}」発動！"
            )
            if opponent_hand:
                game.turn_step = "PSY_DISCARD_SELECTION"
                game.log_message = (
                    start_message
                    if is_cpu
                    else start_message
                    + "捨てる相手の伏せカードを選んでください。"
                )
            else:
                game.end_action(
                    role,
                    start_message + "しかし相手の手札は空だった",
                )
            return

        if ability_name == "ヒーリング":
            start_message = (
                f"CPUが「{ability_display}」を発動！"
                if is_cpu
                else f"「{ability_display}」発動！"
            )
            if (
                not game.get_flat_discard("p1")
                and not game.get_flat_discard("p2")
            ):
                game.end_action(
                    role,
                    start_message + "しかし捨て札がなかった",
                )
                return
            game.turn_step = "REGEN_SELECTION"
            game.temp_selection = []
            game.regen_pool = GameService._build_regen_pool(game)
            game.log_message = (
                start_message
                if is_cpu
                else start_message + "山札に戻すカードを選んでください。"
            )
            return

        if ability_name == "クレヤボヤンス":
            start_message = (
                f"CPUが「{ability_display}」を発動！"
                if is_cpu
                else f"「{ability_display}」発動！"
            )
            game.turn_step = "CLAIR_SELECTION"
            game.temp_selection = []
            game.clair_pool = GameService._build_clair_pool(
                game,
                role,
                cpu=is_cpu,
            )
            if not game.clair_pool:
                game.end_action(
                    role,
                    start_message + "しかし対象になるカードがなかった",
                )
            else:
                game.log_message = (
                    start_message
                    if is_cpu
                    else start_message + "透視するカードを選んでください。"
                )
            return

        if ability_name == "プリサイエンス":
            count = min(3, len(game.deck))
            if count == 0:
                start_message = (
                    f"CPUが「{ability_display}」を発動！"
                    if is_cpu
                    else f"「{ability_display}」発動！"
                )
                game.end_action(
                    role,
                    start_message + "しかし山札が空だった",
                )
                return
            game.prescience_cards = [
                game.deck.pop() for _ in range(count)
            ]
            game.prescience_ordered = []
            game.turn_step = "PRESCIENCE_SELECT_1"
            if not is_cpu:
                game.log_message = (
                    f"「{ability_display}」発動！"
                    "一番上に配置するカードを選んでください。"
                )
            return

        if ability_name == "タイムリープ":
            game.extra_turn = True
            game.fill_hand_to_6(role)
            if is_cpu:
                message = (
                    f"CPUが「{ability_display}」を発動！追加ターンを得た"
                )
            else:
                message = (
                    f"「{ability_display}」発動！"
                    f"{player_name} は追加ターンを得た"
                )
            game.end_action(role, message)

    @staticmethod
    def _finish_prescience(
        game: EsperGame,
        role: str,
        player_name: str,
    ) -> None:
        ordered_cards = game.prescience_ordered + game.prescience_cards
        game.deck.extend(reversed(ordered_cards))
        game.prescience_ordered = []
        game.prescience_cards = []
        game.fill_hand_to_6(role)

        if GameService._is_cpu_actor(game, role):
            message = (
                "CPUが「プリサイエンス(未来予知)」を発動し、"
                "未来を覗き見た！"
            )
        else:
            message = (
                "「プリサイエンス(未来予知)」発動！"
                f"{player_name} は未来を覗き見た！"
            )
        game.end_action(role, message)

    @staticmethod
    def _build_regen_pool(game: EsperGame) -> list[dict]:
        pool = []
        for owner in ("p1", "p2"):
            for group_index, group in enumerate(
                game.get_discard_groups(owner)
            ):
                for item_index, card in enumerate(group):
                    pool.append({
                        "owner": owner,
                        "g_idx": group_index,
                        "item_idx": item_index,
                        "name": card["name"],
                        "is_face_up": card["is_face_up"],
                    })
        return pool

    @staticmethod
    def _build_clair_pool(
        game: EsperGame,
        role: str,
        *,
        cpu: bool,
    ) -> list[dict]:
        opponent_role = game.get_op_role(role)
        opponent_hand = game.get_hand(opponent_role)
        display_hand = (
            list(opponent_hand)
            if cpu
            else game.sort_hand(opponent_hand)
        )
        pool = []
        for index, card in enumerate(display_hand):
            label = (
                "あなたの伏せ手札"
                if cpu
                else f"相手の伏せ手札 {index + 1}"
            )
            pool.append({
                "type": "hand",
                "idx": index,
                "name": card,
                "label": label,
            })

        for group_index, group in enumerate(
            game.get_discard_groups(opponent_role)
        ):
            if not group[0]["is_face_up"]:
                label = (
                    "あなたの裏向き捨て札"
                    if cpu
                    else f"相手の裏向き捨て札 {group_index + 1}"
                )
                pool.append({
                    "type": "discard",
                    "g_idx": group_index,
                    "name": group[0]["name"],
                    "label": label,
                })
        return pool

    @staticmethod
    def _return_discard_items_to_deck(
        game: EsperGame,
        selected_items: list[dict],
    ) -> None:
        def sort_key(item: dict) -> tuple[int, int]:
            return item["g_idx"], item["item_idx"]

        for owner in ("p1", "p2"):
            items = sorted(
                (
                    item
                    for item in selected_items
                    if item["owner"] == owner
                ),
                key=sort_key,
                reverse=True,
            )
            groups = game.get_discard_groups(owner)
            for item in items:
                card = groups[item["g_idx"]].pop(item["item_idx"])
                game.deck.append(card["name"])
                if not groups[item["g_idx"]]:
                    groups.pop(item["g_idx"])

    @staticmethod
    def _is_cpu_actor(game: EsperGame, role: str) -> bool:
        return game.is_cpu and role == "p2"
