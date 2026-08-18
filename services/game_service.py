"""プレイヤー操作によるゲーム状態の変更を集約するサービス。

このファイルは「ルール上の操作」を実際の EsperGame 状態変更へ変換する。
HTTPやWebSocketのことは知らず、カードの移動、ターン遷移、通知文の作成だけを扱う。
"""

import random

from game_logic import EsperGame


# UIやログでは能力名に読みを添えて表示するため、内部名から表示名へ変換する。
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
    """UIに依存しないゲーム操作を提供する。

    ここにあるメソッドはすべて「操作を受け取った後の状態更新」を担当する。
    操作可能かどうかの検証は CommandService/StateService 側で済ませる。
    """

    @staticmethod
    def _actor_name(game: EsperGame, role: str) -> str:
        """通知文で使う役割名をゲーム状態から取得する。"""
        return game.get_player_name(role)

    @staticmethod
    def _ability_title(
        game: EsperGame,
        role: str,
        ability_name: str,
    ) -> str:
        """通常発動とカモフラージュ発動で通知タイトルを出し分ける。"""
        actor = GameService._actor_name(game, role)
        active = game.active_ability or {}
        if (
            active.get("role") == role
            and active.get("name") == ability_name
            and active.get("mimic")
        ):
            return (
                f"{actor}がカモフラージュで"
                f"「{NAME_MAP.get(ability_name, ability_name)}」を発動"
            )
        return f"{actor}が「{NAME_MAP.get(ability_name, ability_name)}」を発動"

    @staticmethod
    def _emit_ability_event(
        game: EsperGame,
        role: str,
        ability_name: str,
        detail_by_role: dict[str, str],
        *,
        tone_by_role: dict[str, str] | None = None,
        kind: str = "ability",
        duration_ms: int = 3000,
    ) -> None:
        """能力演出用イベントを登録し、解決中能力の一時情報を片付ける。"""
        game.add_action_event(
            role,
            kind,
            GameService._ability_title(game, role, ability_name),
            detail_by_role,
            tone="ability",
            tone_by_role=tone_by_role,
            duration_ms=duration_ms,
        )
        game.active_ability = None

    @staticmethod
    def start_turn_timer(game: EsperGame) -> bool:
        """先攻抽選タイマーが二重に走らないよう、開始済みならFalseを返す。"""
        if getattr(game, "timer_started", False):
            return False
        game.timer_started = True
        return True

    @staticmethod
    def decide_first_player(game: EsperGame) -> str:
        """先攻をランダムに決め、最初の捨て札ステップへ進める。"""
        game.current_turn = random.choice(["p1", "p2"])
        game.turn_step = "DISCARD"
        game.start_turn(game.current_turn)
        first_player_name = game.get_player_name(game.current_turn)
        game.add_log(
            None,
            f"🎉 抽選結果：【{first_player_name}】の先攻でスタート！",
        )
        return game.current_turn

    @staticmethod
    def declare_esper(game: EsperGame, role: str, player_name: str) -> None:
        """ESPER宣言による即時勝利を確定する。"""
        game.add_log(
            role,
            f"🎉【決着】{player_name} が「エスパー！」を宣言しました！",
        )
        game.extra_turn = False
        game.extra_turn_chain = 0
        game.winner_role = role
        game.result_reason = "ESPERを宣言"
        game.end_trigger_reason = "ESPERを宣言"
        game.turn_step = "GAME_CLEAR"

    @staticmethod
    def discard_card(
        game: EsperGame,
        role: str,
        card: str,
        player_name: str,
    ) -> None:
        """手札から1枚を捨て札グループに移し、補充待ちステップへ進める。"""
        hand = game.get_hand(role)
        hand.remove(card)

        discard_groups = game.get_discard_groups(role)
        face_down_count = sum(
            1
            for group in discard_groups
            for item in group
            if not item["is_face_up"]
        )
        # 通常捨て札は、自分の裏向き捨て札が5枚になるまでは伏せて置く。
        is_face_up = face_down_count >= 5
        discard_groups.append(
            [{
                "name": card,
                "is_face_up": is_face_up,
                "owner": role,
            }]
        )
        game.pending_discards[role] = {
            "card": card,
            "is_face_up": is_face_up,
        }

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
        """山札から手札を6枚まで補充し、能力使用判断ステップへ進める。"""
        before_count = len(game.get_hand(role))
        game.fill_hand_to_6(role)
        drawn_count = len(game.get_hand(role)) - before_count
        pending = game.pending_discards.pop(role, None)
        # 捨て札と補充は別アクションなので、補充時にまとめて見やすい通知を出す。
        if pending is not None:
            opponent_role = game.get_op_role(role)
            discarded_card = pending["card"]
            public_discard = (
                f"「{discarded_card}」を捨て、"
                if pending["is_face_up"]
                else "手札を1枚捨て、"
            )
            draw_text = (
                f"山札から{drawn_count}枚引きました"
                if drawn_count != 1
                else "山札から1枚引きました"
            )
            game.add_action_event(
                role,
                "hand_refresh",
                f"{GameService._actor_name(game, role)}が手札を入れ替えました",
                {
                    role: f"「{discarded_card}」を捨て、{draw_text}",
                    opponent_role: public_discard + draw_text,
                },
                tone="normal",
                duration_ms=2000,
            )
        if GameService._is_cpu_actor(game, role):
            game.add_log(role, "CPUが手札を補充しました。")
        else:
            game.log_message = (
                f"{player_name} が手札を補充しました。能力を使いますか？"
            )
        game.turn_step = "THINK"

    @staticmethod
    def open_ability_selection(game: EsperGame) -> None:
        """能力候補を選ぶモーダル表示用の状態へ進める。"""
        game.turn_step = "ABILITY"

    @staticmethod
    def cancel_ability_selection(game: EsperGame) -> None:
        """能力選択をやめ、能力を使うかパスするかの判断ステップへ戻す。"""
        game.turn_step = "THINK"

    @staticmethod
    def open_mimic_selection(game: EsperGame) -> None:
        """カモフラージュで擬態する能力を選ぶ状態へ進める。"""
        game.turn_step = "MIMIC_SELECTION"

    @staticmethod
    def cancel_mimic_selection(game: EsperGame) -> None:
        """擬態先選択をやめ、通常の能力選択へ戻す。"""
        game.turn_step = "ABILITY"

    @staticmethod
    def pass_turn(
        game: EsperGame,
        role: str,
        player_name: str,
        *,
        cpu: bool = False,
    ) -> None:
        """能力を使わずにターンを終える。CPU時だけ表示文を短く変える。"""
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
        """能力コストを手札から捨て札へ移し、能力ごとの解決処理へ振り分ける。"""
        game.active_ability = {
            "role": role,
            "name": ability_name,
            "mimic": mimic,
        }
        hand = game.get_hand(role)
        if mimic:
            # 擬態はカモフラージュ2枚と、実際にまねる能力カード1枚を表向きで支払う。
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
            # 通常発動は同名2枚を表向きで支払う。
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
        """宣言した能力名を相手手札からすべて捨てさせ、双方を6枚へ補充する。"""
        opponent_role = game.get_op_role(role)
        hand = game.get_hand(role)
        opponent_hand = game.get_hand(opponent_role)
        removed_count = opponent_hand.count(target_name)
        my_needs = 6 - len(hand)
        opponent_needs = 6 - (len(opponent_hand) - removed_count)

        # 効果後に両者が必要枚数を補充できない場合は、途中状態を作らず引き分け終了にする。
        if my_needs + opponent_needs > len(game.deck):
            GameService._emit_ability_event(
                game,
                role,
                "テレポート",
                {
                    role: "補充に必要な山札が足りませんでした",
                    opponent_role: "補充に必要な山札が足りませんでした",
                },
            )
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
        victim_detail = (
            f"あなたの「{target_display}」{removed_count}枚が捨てられ、"
            f"山札から{opponent_needs}枚補充されました"
            if removed_count
            else f"「{target_display}」を宣言しましたが、該当カードはありませんでした"
        )
        GameService._emit_ability_event(
            game,
            role,
            "テレポート",
            {
                role: (
                    f"「{target_display}」を宣言し、"
                    f"相手のカードを{removed_count}枚捨てさせました"
                ),
                opponent_role: victim_detail,
            },
            tone_by_role={
                opponent_role: "impact" if removed_count else "ability",
            },
        )
        game.end_action(role, message)

    @staticmethod
    def psychokinesis_discard(
        game: EsperGame,
        role: str,
        target_card: str,
        player_name: str,
    ) -> None:
        """念力の1段目として、相手手札1枚を表向きで捨てさせる。"""
        opponent_role = game.get_op_role(role)
        opponent_hand = game.get_hand(opponent_role)
        opponent_groups = game.get_discard_groups(opponent_role)

        opponent_hand.remove(target_card)
        if game.active_ability is None:
            game.active_ability = {
                "role": role,
                "name": "サイコキネシス",
                "mimic": False,
            }
        game.active_ability["psych_discarded_card"] = target_card
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
        # 2段目の対象がない場合、1段目の捨て札も取り消して通常のターン終了へ進む。
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
            GameService._emit_ability_event(
                game,
                role,
                "サイコキネシス",
                {
                    role: "戻せる裏向きの捨て札がありませんでした",
                    opponent_role: (
                        f"あなたの「{target_card}」が選ばれましたが、"
                        "戻せる捨て札がないため手札へ戻りました"
                    ),
                },
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
        """念力の2段目として、相手の裏向き捨て札1枚を相手手札へ戻す。"""
        opponent_role = game.get_op_role(role)
        opponent_groups = game.get_discard_groups(opponent_role)
        target_name = opponent_groups.pop(group_index)[0]["name"]
        discarded_card = (game.active_ability or {}).get(
            "psych_discarded_card",
            "手札1枚",
        )
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
        GameService._emit_ability_event(
            game,
            role,
            "サイコキネシス",
            {
                role: (
                    f"相手の「{discarded_card}」を捨てさせ、"
                    "裏向きの捨て札1枚を相手の手札へ戻しました"
                ),
                opponent_role: (
                    f"あなたの「{discarded_card}」が捨てられ、"
                    f"捨て札の「{target_name}」が手札へ戻りました"
                ),
            },
            tone_by_role={opponent_role: "impact"},
        )
        game.end_action(role, message)

    @staticmethod
    def toggle_healing_selection(game: EsperGame, target_index: int) -> None:
        """ヒーリング対象を最大3枚までトグル選択する。"""
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
        """選択した捨て札を山札へ戻してシャッフルし、手札を補充する。"""
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

        opponent_role = game.get_op_role(role)
        detail_by_role = {}
        tone_by_role = {}
        for viewer_role in (role, opponent_role):
            descriptions = []
            for item in selected_items:
                owner = "あなた" if item["owner"] == viewer_role else "相手"
                visible = item["is_face_up"] or item["owner"] == viewer_role
                card_name = item["name"]
                card = f"「{card_name}」" if visible else "裏向きのカード"
                descriptions.append(f"{owner}の{card}")
            joined_descriptions = "、".join(descriptions)
            detail_by_role[viewer_role] = (
                f"{joined_descriptions}を山札に戻しました"
                if descriptions
                else "山札へ戻すカードはありませんでした"
            )
            if any(item["owner"] == viewer_role for item in selected_items):
                tone_by_role[viewer_role] = "impact"
        GameService._emit_ability_event(
            game,
            role,
            "ヒーリング",
            detail_by_role,
            tone_by_role=tone_by_role,
        )
        game.temp_selection = []
        game.end_action(role, message)

    @staticmethod
    def toggle_clairvoyance_selection(
        game: EsperGame,
        target_index: int,
    ) -> None:
        """クレヤボヤンス対象を最大2枚までトグル選択する。"""
        if target_index in game.temp_selection:
            game.temp_selection.remove(target_index)
        elif len(game.temp_selection) < 2:
            game.temp_selection.append(target_index)

    @staticmethod
    def confirm_clairvoyance(game: EsperGame) -> None:
        """選択した透視対象を一時的に公開する確認ステップへ進める。"""
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
        """透視結果の確認を終え、手札補充とターン終了処理へ進める。"""
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
        selected = [
            game.clair_pool[index]
            for index in game.temp_selection
        ]
        hand_count = sum(item["type"] == "hand" for item in selected)
        discard_count = sum(item["type"] == "discard" for item in selected)
        targets = []
        if hand_count:
            targets.append(f"手札{hand_count}枚")
        if discard_count:
            targets.append(f"捨て札{discard_count}枚")
        target_text = "と".join(targets) if targets else "カード0枚"
        revealed_cards = [
            (
                "手札" if item["type"] == "hand" else "捨て札",
                item["name"],
            )
            for item in selected
        ]
        revealed_text = "と".join(
            f"{zone}の「{card_name}」"
            for zone, card_name in revealed_cards
        )
        opponent_role = game.get_op_role(role)
        GameService._emit_ability_event(
            game,
            role,
            "クレヤボヤンス",
            {
                role: f"相手の{target_text}を透視しました",
                opponent_role: (
                    f"あなたの{revealed_text}が透視されました"
                    if revealed_text
                    else "あなたのカードは透視されませんでした"
                ),
            },
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
        """旧UI互換の1枚ずつ選択方式で、未来予知の戻し順を記録する。"""
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
        """画面で並べた順序を一括で受け取り、未来予知を完了する。"""
        game.prescience_ordered = [
            game.prescience_cards[index]
            for index in ordered_indices
        ]
        game.prescience_cards = []
        GameService._finish_prescience(game, role, player_name)

    @staticmethod
    def send_chat(game: EsperGame, player_name: str, message: str) -> bool:
        """空文字でなければ表示名付きのチャット履歴として保存する。"""
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
        """能力名ごとに、即時解決か追加選択ステップかを決める。"""
        ability_display = NAME_MAP.get(ability_name, ability_name)
        opponent_role = game.get_op_role(role)
        opponent_hand = game.get_hand(opponent_role)
        is_cpu = GameService._is_cpu_actor(game, role)

        if ability_name == "テレポート":
            # テレポートはプレイヤーが宣言する能力名を追加で選ぶ。
            game.turn_step = "TELEPORT_SELECTION"
            return

        if ability_name == "サイコキネシス":
            # サイコキネシスは「手札を捨てさせる」「裏向き捨て札を戻す」の2段階。
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
                GameService._emit_ability_event(
                    game,
                    role,
                    ability_name,
                    {
                        role: "相手の手札が空のため対象がありませんでした",
                        opponent_role: "手札が空のため効果を受けませんでした",
                    },
                )
                game.end_action(
                    role,
                    start_message + "しかし相手の手札は空だった",
                )
            return

        if ability_name == "ヒーリング":
            # ヒーリングは両者の捨て札を候補化し、最大3枚を選ばせる。
            start_message = (
                f"CPUが「{ability_display}」を発動！"
                if is_cpu
                else f"「{ability_display}」発動！"
            )
            if (
                not game.get_flat_discard("p1")
                and not game.get_flat_discard("p2")
            ):
                GameService._emit_ability_event(
                    game,
                    role,
                    ability_name,
                    {
                        role: "捨て札がないため何も戻しませんでした",
                        opponent_role: "捨て札がないため何も戻りませんでした",
                    },
                )
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
            # クレヤボヤンスは相手手札と裏向き捨て札を候補化し、選択後だけ公開する。
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
                GameService._emit_ability_event(
                    game,
                    role,
                    ability_name,
                    {
                        role: "透視できるカードがありませんでした",
                        opponent_role: "透視できるカードがないため効果を受けませんでした",
                    },
                )
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
            # プリサイエンスは山札の上から最大3枚を抜き、選んだ順に戻す。
            count = min(3, len(game.deck))
            if count == 0:
                start_message = (
                    f"CPUが「{ability_display}」を発動！"
                    if is_cpu
                    else f"「{ability_display}」発動！"
                )
                GameService._emit_ability_event(
                    game,
                    role,
                    ability_name,
                    {
                        role: "山札が空のため並べ替えられませんでした",
                        opponent_role: "山札が空のため効果はありませんでした",
                    },
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
            # タイムリープだけは追加選択なしで、次のend_action時に同じ人のターンを作る。
            game.extra_turn = True
            game.fill_hand_to_6(role)
            next_chain = game.extra_turn_chain + 1
            GameService._emit_ability_event(
                game,
                role,
                ability_name,
                {
                    role: f"追加ターンを獲得しました（連続{next_chain}回目）",
                    opponent_role: f"追加ターンが始まります（連続{next_chain}回目）",
                },
                kind="time_leap",
                duration_ms=2000,
            )
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
        """並べ替え済みカードを山札上に戻し、未来予知の一時状態を消す。"""
        ordered_cards = game.prescience_ordered + game.prescience_cards
        # 山札末尾を一番上として扱うため、選択順を逆向きにextendする。
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
        opponent_role = game.get_op_role(role)
        count = len(ordered_cards)
        GameService._emit_ability_event(
            game,
            role,
            "プリサイエンス",
            {
                role: f"山札の上{count}枚を好きな順番に並べ替えました",
                opponent_role: f"山札の上{count}枚を並べ替えました",
            },
        )
        game.end_action(role, message)

    @staticmethod
    def _build_regen_pool(game: EsperGame) -> list[dict]:
        """ヒーリングで選べる全捨て札を、元の位置付きで列挙する。"""
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
        """クレヤボヤンスで透視できる相手手札と裏向き捨て札を列挙する。"""
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
        """選択済み捨て札を元のグループから抜き、カード名だけを山札へ戻す。"""
        def sort_key(item: dict) -> tuple[int, int]:
            return item["g_idx"], item["item_idx"]

        for owner in ("p1", "p2"):
            # 同じグループから複数枚抜く場合にindexがずれないよう、後ろから削除する。
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
        """p2がCPUとして動いている場面かどうかを返す。"""
        return game.is_cpu and role == "p2"
