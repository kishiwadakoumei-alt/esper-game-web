"""CPUプレイヤーの判断と1ステップ分の操作を管理するサービス。

CPUはp2固定で動く。難易度ごとの判断はこのファイルに閉じ込め、
実際の状態更新は人間と同じGameServiceを使う。
"""

import random
from collections import Counter

from game_logic import EsperGame
from services.game_service import GameService


class CpuService:
    """画面処理から独立したCPU操作を提供する。

    take_stepは現在のturn_stepを1つだけ進める。複数ステップ必要な能力は
    ApplicationContext._run_cpuがループして続きのステップを呼ぶ。
    """

    # CPUが自動操作してよいターン状態。終局や待機状態は含めない。
    ACTIVE_STEPS = [
        "DISCARD",
        "DRAW",
        "THINK",
        "ABILITY",
        "TELEPORT_SELECTION",
        "PSY_DISCARD_SELECTION",
        "PSY_PUSH_SELECTION",
        "REGEN_SELECTION",
        "CLAIR_SELECTION",
        "CLAIR_REVEAL",
        "PRESCIENCE_SELECT_1",
        "PRESCIENCE_SELECT_2",
    ]

    @classmethod
    def can_act(cls, game: EsperGame) -> bool:
        """CPU戦かつp2の操作待ちならTrueを返す。"""
        return (
            game.is_cpu
            and game.current_turn == "p2"
            and game.turn_step in cls.ACTIVE_STEPS
        )

    @classmethod
    def begin_action(cls, game: EsperGame) -> bool:
        """CPU行動の開始フラグを立て、多重実行を防ぐ。"""
        if not cls.can_act(game) or game.cpu_acting:
            return False
        game.cpu_acting = True
        return True

    @staticmethod
    def finish_action(game: EsperGame) -> None:
        """CPU行動フラグを下げ、次のCPUステップを予約できる状態に戻す。"""
        game.cpu_acting = False

    @classmethod
    def take_step(cls, game: EsperGame) -> None:
        """現在のturn_stepに応じて、CPUの操作を1つだけ実行する。"""
        level = getattr(game, "cpu_level", "normal")

        # CPUも人間と同じく、条件を満たしたら自分の番以外の処理途中でも宣言できる。
        if (
            game.turn_step not in ["GAME_CLEAR", "GAME_OVER"]
            and game.check_esper(game.p2_hand)
        ):
            GameService.declare_esper(
                game,
                "p2",
                "CPU",
            )
            return

        if game.turn_step == "DISCARD":
            card = cls._choose_discard(game, level)
            GameService.discard_card(game, "p2", card, "CPU")
            return

        if game.turn_step == "DRAW":
            GameService.draw_hand(game, "p2", "CPU")
            return

        if game.turn_step == "THINK":
            cls._think(game, level)
            return

        if game.turn_step == "ABILITY":
            cls._activate_ability(game)
            return

        if game.turn_step == "TELEPORT_SELECTION":
            target_name = cls._choose_teleport_target(game, level)
            GameService.teleport(game, "p2", target_name, "CPU")
            return

        if game.turn_step == "PSY_DISCARD_SELECTION":
            target_card = random.choice(game.p1_hand)
            GameService.psychokinesis_discard(
                game,
                "p2",
                target_card,
                "CPU",
            )
            return

        if game.turn_step == "PSY_PUSH_SELECTION":
            candidates = [
                group_index
                for group_index, group in enumerate(
                    game.p1_discard_groups
                )
                if len(group) == 1 and not group[0]["is_face_up"]
            ]
            GameService.psychokinesis_push(
                game,
                "p2",
                random.choice(candidates),
                "CPU",
            )
            return

        if game.turn_step == "REGEN_SELECTION":
            game.temp_selection = cls._choose_healing_cards(game, level)
            GameService.confirm_healing(game, "p2", "CPU")
            return

        if game.turn_step == "CLAIR_SELECTION":
            count = min(2, len(game.clair_pool))
            game.temp_selection = random.sample(
                range(len(game.clair_pool)),
                count,
            )
            GameService.confirm_clairvoyance(game)
            return

        if game.turn_step == "CLAIR_REVEAL":
            GameService.finish_clairvoyance(game, "p2", "CPU")
            return

        if game.turn_step in [
            "PRESCIENCE_SELECT_1",
            "PRESCIENCE_SELECT_2",
        ]:
            target_index = cls._choose_prescience_card(game, level)
            GameService.choose_prescience_card(
                game,
                "p2",
                target_index,
                "CPU",
            )

    @staticmethod
    def _choose_discard(game: EsperGame, level: str) -> str:
        """難易度に応じて、CPUが捨てるカードを選ぶ。"""
        if level != "hard":
            return random.choice(game.p2_hand)

        counts = Counter(game.p2_hand)
        if counts.get("カモフラージュ", 0) >= 3:
            # hardはカモフラージュを抱え込みすぎないよう、余剰分を捨てやすくする。
            return "カモフラージュ"

        candidates = [
            card
            for card in game.p2_hand
            if card != "カモフラージュ"
        ]
        if not candidates:
            candidates = game.p2_hand
        minimum_count = min(counts[card] for card in candidates)
        minimum_candidates = [
            card
            for card in candidates
            if counts[card] == minimum_count
        ]
        return random.choice(minimum_candidates)

    @staticmethod
    def _think(game: EsperGame, level: str) -> None:
        """能力を使うか、ターンを終了するかを難易度ごとに判断する。"""
        if level == "easy":
            GameService.pass_turn(
                game,
                "p2",
                "CPU",
                cpu=True,
            )
            return

        counts = Counter(game.p2_hand)
        usable = []
        for card, count in counts.items():
            if count < 2 or card == "カモフラージュ":
                continue
            if len(game.deck) <= 1 and card != "ヒーリング":
                continue
            usable.append(card)

        chance = 0.7 if level == "normal" else 0.95
        if usable and random.random() < chance:
            GameService.open_ability_selection(game)
        else:
            GameService.pass_turn(
                game,
                "p2",
                "CPU",
                cpu=True,
            )

    @staticmethod
    def _activate_ability(game: EsperGame) -> None:
        """現在手札で使える通常能力からランダムに1つ発動する。"""
        counts = Counter(game.p2_hand)
        usable = [
            card
            for card, count in counts.items()
            if count >= 2 and card != "カモフラージュ"
        ]
        if not usable:
            return
        GameService.activate_ability(
            game,
            "p2",
            random.choice(usable),
            "CPU",
        )

    @staticmethod
    def _choose_teleport_target(
        game: EsperGame,
        level: str,
    ) -> str:
        """テレポートで宣言する能力名を選ぶ。hardは見えていない枚数が多い能力を狙う。"""
        if level != "hard":
            return random.choice(game.types)

        # hardは自分の手札・表向き捨て札・ゲーム外カードから見えている枚数を数える。
        visible_counts = Counter()
        for card in game.p2_hand:
            visible_counts[card] += 1
        for group in game.p2_discard_groups:
            for card in group:
                if card["is_face_up"]:
                    visible_counts[card["name"]] += 1
        for group in game.p1_discard_groups:
            for card in group:
                if card["is_face_up"]:
                    visible_counts[card["name"]] += 1
        for card in game.excluded_cards:
            visible_counts[card] += 1

        best_target = game.types[0]
        max_invisible = -1
        for card_type in game.types:
            invisible = 8 - visible_counts[card_type]
            if invisible > max_invisible:
                max_invisible = invisible
                best_target = card_type
        return best_target

    @staticmethod
    def _choose_healing_cards(
        game: EsperGame,
        level: str,
    ) -> list[int]:
        """ヒーリングで戻すカードを選ぶ。hardは自分の手札に合う種類を優先する。"""
        count = min(3, len(game.regen_pool))
        if level != "hard":
            return random.sample(range(len(game.regen_pool)), count)

        hand_types = set(game.p2_hand)
        priority_items = []
        normal_items = []
        for index, item in enumerate(game.regen_pool):
            if (
                item["name"] in hand_types
                or item["name"] == "カモフラージュ"
            ):
                priority_items.append(index)
            else:
                normal_items.append(index)
        random.shuffle(priority_items)
        random.shuffle(normal_items)
        return (priority_items + normal_items)[:count]

    @staticmethod
    def _choose_prescience_card(
        game: EsperGame,
        level: str,
    ) -> int:
        """未来予知で次に山札上へ置くカードを選ぶ。hardは自分に有利な種類を優先する。"""
        if level != "hard":
            return random.randrange(len(game.prescience_cards))

        hand_types = set(game.p2_hand)
        for index, card in enumerate(game.prescience_cards):
            if card in hand_types or card == "カモフラージュ":
                return index
        return 0
