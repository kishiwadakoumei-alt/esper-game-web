import re
import unittest
from collections import Counter
from unittest.mock import patch

from game_logic import EsperGame


class EsperGameInitializationTests(unittest.TestCase):
    def test_initial_state_preserves_all_cards(self):
        game = EsperGame()

        self.assertEqual(len(game.types), 7)
        self.assertEqual(len(game.excluded_cards), 3)
        self.assertEqual(len(game.p1_hand), 6)
        self.assertEqual(len(game.p2_hand), 6)
        self.assertEqual(len(game.deck), 41)
        self.assertEqual(game.current_turn, "p1")
        self.assertEqual(game.turn_step, "WAITING")

        all_cards = (
            game.deck
            + game.excluded_cards
            + game.p1_hand
            + game.p2_hand
        )
        self.assertEqual(len(all_cards), 56)
        self.assertEqual(
            Counter(all_cards),
            Counter({card_type: 8 for card_type in game.types}),
        )

    def test_initial_deal_can_be_made_deterministic(self):
        with patch("game_logic.random.shuffle", side_effect=lambda cards: None):
            game = EsperGame()

        self.assertEqual(
            game.excluded_cards,
            ["クレヤボヤンス", "クレヤボヤンス", "クレヤボヤンス"],
        )
        self.assertEqual(game.p1_hand, ["カモフラージュ"] * 6)
        self.assertEqual(
            Counter(game.p2_hand),
            Counter({"カモフラージュ": 2, "ヒーリング": 4}),
        )


class EsperGameHandTests(unittest.TestCase):
    def setUp(self):
        self.game = EsperGame()

    def test_sort_hand_orders_by_count_then_name(self):
        hand = ["b", "a", "c", "a", "b", "b"]

        self.assertEqual(self.game.sort_hand(hand), ["b", "b", "b", "a", "a", "c"])
        self.assertEqual(hand, ["b", "a", "c", "a", "b", "b"])

    def test_check_esper_uses_two_camouflage_as_one_wildcard(self):
        cases = [
            (["A"] * 5, True),
            (["カモフラージュ"] * 5, True),
            (["A"] * 4 + ["カモフラージュ"] * 2, True),
            (["A"] * 4 + ["カモフラージュ"], False),
            (["A"] * 3 + ["カモフラージュ"] * 4, True),
            (["A"] * 2 + ["カモフラージュ"] * 4, False),
            (["カモフラージュ"] * 4, False),
            ([], False),
        ]

        for hand, expected in cases:
            with self.subTest(hand=hand):
                self.assertEqual(self.game.check_esper(hand), expected)

    def test_fill_hand_to_6_draws_only_until_six(self):
        self.game.p1_hand = ["A", "B", "C"]
        self.game.deck = ["D", "E", "F", "G"]

        self.game.fill_hand_to_6("p1")

        self.assertEqual(self.game.p1_hand, ["A", "B", "C", "G", "F", "E"])
        self.assertEqual(self.game.deck, ["D"])

        self.game.p1_hand.append("H")
        self.game.fill_hand_to_6("p1")
        self.assertEqual(len(self.game.p1_hand), 7)
        self.assertEqual(self.game.deck, ["D"])

    def test_role_and_discard_helpers_return_expected_data(self):
        self.game.p1_hand = ["P1"]
        self.game.p2_hand = ["P2"]
        self.game.p1_discard_groups = [
            [{"name": "A"}],
            [{"name": "B"}, {"name": "C"}],
        ]
        self.game.players = ["Alice", "Bob"]

        self.assertIs(self.game.get_hand("p1"), self.game.p1_hand)
        self.assertIs(self.game.get_hand("p2"), self.game.p2_hand)
        self.assertIs(
            self.game.get_discard_groups("p1"),
            self.game.p1_discard_groups,
        )
        self.assertEqual(self.game.get_op_role("p1"), "p2")
        self.assertEqual(self.game.get_op_role("p2"), "p1")
        self.assertEqual(
            self.game.get_flat_discard("p1"),
            [{"name": "A"}, {"name": "B"}, {"name": "C"}],
        )
        self.assertEqual(self.game.get_player_name("p1"), "Alice")
        self.assertEqual(self.game.get_player_name("p2"), "Bob")


class EsperGameLogAndEndgameTests(unittest.TestCase):
    def setUp(self):
        self.game = EsperGame()
        self.game.players = ["Alice", "Bob"]
        self.game.log_history = []

    def test_add_log_records_actor_and_latest_message(self):
        self.game.add_log("p1", "カードを捨てました")

        self.assertEqual(self.game.log_message, "カードを捨てました")
        self.assertEqual(len(self.game.log_history), 1)
        entry = self.game.log_history[0]
        self.assertTrue(re.fullmatch(r"\d{2}:\d{2}", entry["time"]))
        self.assertEqual(entry["role"], "p1")
        self.assertEqual(entry["name"], "Alice")
        self.assertEqual(entry["icon"], "👤")
        self.assertEqual(entry["text"], "カードを捨てました")

    def test_trigger_endgame_prioritizes_esper(self):
        self.game.p1_hand = ["A"] * 5 + ["B"]
        self.game.p2_hand = ["C"] * 4 + ["D"] * 2

        self.game.trigger_endgame("テスト終了")

        self.assertEqual(self.game.turn_step, "GAME_OVER")
        self.assertIn("ESPER達成", self.game.log_message)
        self.assertIn("Alice の大勝利", self.game.log_message)

    def test_trigger_endgame_compares_group_sizes_lexicographically(self):
        self.game.p1_hand = ["A"] * 3 + ["B"] * 2 + ["C"]
        self.game.p2_hand = ["A"] * 2 + ["B"] * 2 + ["C"] * 2

        self.game.trigger_endgame("テスト終了")

        self.assertIn("Alice の勝利", self.game.log_message)
        self.assertIn("3枚・2枚・1枚 対 2枚・2枚・2枚", self.game.log_message)

    def test_trigger_endgame_draws_when_both_players_have_esper(self):
        self.game.p1_hand = ["A"] * 5 + ["B"]
        self.game.p2_hand = ["C"] * 5 + ["D"]

        self.game.trigger_endgame("テスト終了")

        self.assertIn("完全引き分け", self.game.log_message)

    def test_trigger_draw_sets_game_over_and_system_log(self):
        self.game.trigger_draw("補充するカードが足りません")

        self.assertEqual(self.game.turn_step, "GAME_OVER")
        self.assertIn("【引き分け】", self.game.log_message)
        self.assertIsNone(self.game.log_history[-1]["role"])


class EsperGameTurnTests(unittest.TestCase):
    def setUp(self):
        self.game = EsperGame()
        self.game.players = ["Alice", "Bob"]
        self.game.deck = ["A"]
        self.game.p1_hand = ["B"] * 6
        self.game.p2_hand = ["C"] * 6
        self.game.p1_discard_groups = []
        self.game.p2_discard_groups = []

    def test_end_action_switches_to_opponent(self):
        self.game.current_turn = "p1"

        self.game.end_action("p1", "ターン終了")

        self.assertEqual(self.game.current_turn, "p2")
        self.assertEqual(self.game.turn_step, "DISCARD")
        self.assertEqual(self.game.log_message, "ターン終了")

    def test_end_action_keeps_current_player_for_extra_turn(self):
        self.game.current_turn = "p1"
        self.game.extra_turn = True

        self.game.end_action("p1")

        self.assertEqual(self.game.current_turn, "p1")
        self.assertEqual(self.game.turn_step, "DISCARD")
        self.assertFalse(self.game.extra_turn)
        self.assertEqual(self.game.extra_turn_chain, 1)

    def test_extra_turn_chain_increments_to_four_and_then_resets(self):
        self.game.current_turn = "p1"

        for expected_count in range(1, 5):
            self.game.extra_turn = True
            self.game.end_action("p1")

            self.assertEqual(self.game.current_turn, "p1")
            self.assertEqual(self.game.extra_turn_chain, expected_count)

        self.game.end_action("p1")

        self.assertEqual(self.game.current_turn, "p2")
        self.assertEqual(self.game.extra_turn_chain, 0)

    def test_end_action_ends_game_when_deck_is_empty(self):
        self.game.deck = []

        self.game.end_action("p1")

        self.assertEqual(self.game.turn_step, "GAME_OVER")
        self.assertIn("山札が尽きました", self.game.log_message)

    def test_end_action_ends_game_at_18_discard_groups(self):
        self.game.p1_discard_groups = [
            [{"name": str(index)}] for index in range(18)
        ]

        self.game.end_action("p1")

        self.assertEqual(self.game.turn_step, "GAME_OVER")
        self.assertIn("捨て札が18組", self.game.log_message)


class EsperGameResetTests(unittest.TestCase):
    def test_reset_game_resets_round_state_and_retains_room_state(self):
        with patch("game_logic.random.shuffle", side_effect=lambda cards: None):
            game = EsperGame()

        game.players = ["Alice", "CPU（上級）"]
        game.is_cpu = True
        game.cpu_level = "hard"
        game.current_turn = "p2"
        game.chat_history = ["message"]
        game.log_history = [{"text": "old log"}]
        game.log_message = "old message"
        game.p1_discard_groups = [[{"name": "A"}]]
        game.temp_selection = [1]
        game.regen_pool = [{"name": "A"}]
        game.clair_pool = [{"name": "B"}]
        game.prescience_cards = ["C"]
        game.prescience_ordered = ["D"]
        game.rematch_requests = {"p1", "p2"}
        game.extra_turn = True
        game.extra_turn_chain = 4
        game.cpu_acting = True

        with patch("game_logic.random.shuffle", side_effect=lambda cards: None):
            game.reset_game()

        self.assertEqual(game.turn_step, "DECIDING_TURN")
        self.assertFalse(game.timer_started)
        self.assertFalse(game.cpu_acting)
        self.assertFalse(game.extra_turn)
        self.assertEqual(game.extra_turn_chain, 0)
        self.assertEqual(game.p1_discard_groups, [])
        self.assertEqual(game.p2_discard_groups, [])
        self.assertEqual(game.temp_selection, [])
        self.assertEqual(game.regen_pool, [])
        self.assertEqual(game.clair_pool, [])
        self.assertEqual(game.prescience_cards, [])
        self.assertEqual(game.prescience_ordered, [])
        self.assertEqual(game.rematch_requests, set())

        self.assertEqual(game.players, ["Alice", "CPU（上級）"])
        self.assertTrue(game.is_cpu)
        self.assertEqual(game.cpu_level, "hard")
        self.assertEqual(game.current_turn, "p2")
        self.assertEqual(game.chat_history, ["message"])
        self.assertEqual(game.log_history, [{"text": "old log"}])
        self.assertEqual(game.log_message, "old message")

        all_cards = (
            game.deck
            + game.excluded_cards
            + game.p1_hand
            + game.p2_hand
        )
        self.assertEqual(
            Counter(all_cards),
            Counter({card_type: 8 for card_type in game.types}),
        )


if __name__ == "__main__":
    unittest.main()
