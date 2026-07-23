import unittest
from unittest.mock import patch

from game_logic import EsperGame
from services import CpuService, GameService, RoomService


def make_game() -> EsperGame:
    game = EsperGame()
    game.players = ["Alice", "Bob"]
    game.current_turn = "p1"
    game.turn_step = "DISCARD"
    game.p1_hand = []
    game.p2_hand = []
    game.p1_discard_groups = []
    game.p2_discard_groups = []
    game.deck = []
    game.log_history = []
    game.log_message = ""
    return game


class RoomServiceTests(unittest.TestCase):
    def test_join_room_assigns_roles_and_rejects_third_player(self):
        rooms = {}

        first = RoomService.join_room(rooms, "room", "Alice")
        second = RoomService.join_room(rooms, "room", "Bob")
        third = RoomService.join_room(rooms, "room", "Carol")

        self.assertEqual(first.role, "p1")
        self.assertEqual(second.role, "p2")
        self.assertIsNone(third.role)
        self.assertEqual(third.error, "その部屋はすでに満員です！")
        self.assertEqual(rooms["room"].players, ["Alice", "Bob"])
        self.assertEqual(rooms["room"].turn_step, "DECIDING_TURN")

    def test_create_cpu_room_sets_cpu_metadata(self):
        rooms = {}

        room_id, game = RoomService.create_cpu_room(
            rooms,
            "Alice",
            "hard",
            "上級",
            room_id="cpu-test",
        )

        self.assertEqual(room_id, "cpu-test")
        self.assertIs(rooms[room_id], game)
        self.assertTrue(game.is_cpu)
        self.assertEqual(game.cpu_level, "hard")
        self.assertEqual(game.players, ["Alice", "CPU（上級）"])
        self.assertEqual(game.turn_step, "DECIDING_TURN")

    def test_both_rematch_requests_reset_the_round(self):
        game = make_game()
        game.turn_step = "GAME_OVER"

        first_reset = RoomService.request_rematch(game, "p1")
        second_reset = RoomService.request_rematch(game, "p2")

        self.assertFalse(first_reset)
        self.assertTrue(second_reset)
        self.assertEqual(game.turn_step, "DECIDING_TURN")
        self.assertEqual(game.rematch_requests, set())


class GameServiceTurnTests(unittest.TestCase):
    def test_discard_and_draw_follow_normal_turn_steps(self):
        game = make_game()
        game.p1_hand = ["A", "B", "C", "D", "E", "F"]
        game.deck = ["G"]

        GameService.discard_card(game, "p1", "A", "Alice")

        self.assertEqual(game.turn_step, "DRAW")
        self.assertEqual(game.p1_hand, ["B", "C", "D", "E", "F"])
        self.assertEqual(
            game.p1_discard_groups,
            [[{"name": "A", "is_face_up": False, "owner": "p1"}]],
        )

        GameService.draw_hand(game, "p1", "Alice")

        self.assertEqual(game.turn_step, "THINK")
        self.assertEqual(game.p1_hand, ["B", "C", "D", "E", "F", "G"])
        self.assertEqual(game.deck, [])

    def test_sixth_current_face_down_discard_is_face_up(self):
        game = make_game()
        game.p1_hand = ["A"]
        game.p1_discard_groups = [
            [{"name": str(index), "is_face_up": False, "owner": "p1"}]
            for index in range(5)
        ]

        GameService.discard_card(game, "p1", "A", "Alice")

        self.assertTrue(game.p1_discard_groups[-1][0]["is_face_up"])

    def test_time_leap_consumes_pair_and_keeps_the_turn(self):
        game = make_game()
        game.turn_step = "ABILITY"
        game.p1_hand = ["タイムリープ", "タイムリープ", "A", "B", "C", "D"]
        game.deck = ["REMAIN", "E", "F"]

        GameService.activate_ability(
            game,
            "p1",
            "タイムリープ",
            "Alice",
        )

        self.assertEqual(game.current_turn, "p1")
        self.assertEqual(game.turn_step, "DISCARD")
        self.assertEqual(game.p1_hand, ["A", "B", "C", "D", "F", "E"])
        self.assertEqual(game.deck, ["REMAIN"])
        self.assertEqual(len(game.p1_discard_groups[-1]), 2)


class GameServiceAbilityTests(unittest.TestCase):
    def test_teleport_discards_target_and_refills_both_players(self):
        game = make_game()
        game.turn_step = "TELEPORT_SELECTION"
        game.p1_hand = ["M1", "M2", "M3", "M4"]
        game.p2_hand = ["A", "A", "B", "C", "D", "E"]
        game.deck = ["REMAIN", "D1", "D2", "D3", "D4"]

        GameService.teleport(game, "p1", "A", "Alice")

        self.assertEqual(len(game.p1_hand), 6)
        self.assertEqual(len(game.p2_hand), 6)
        self.assertNotIn("A", game.p2_hand)
        self.assertEqual(len(game.p2_discard_groups[-1]), 2)
        self.assertEqual(game.current_turn, "p2")
        self.assertEqual(game.turn_step, "DISCARD")

    def test_psychokinesis_undoes_discard_without_face_down_target(self):
        game = make_game()
        game.turn_step = "PSY_DISCARD_SELECTION"
        game.p1_hand = ["M1", "M2", "M3", "M4"]
        game.p2_hand = ["A", "B"]
        game.deck = ["REMAIN", "D1", "D2"]

        GameService.psychokinesis_discard(
            game,
            "p1",
            "A",
            "Alice",
        )

        self.assertIn("A", game.p2_hand)
        self.assertEqual(game.p2_discard_groups, [])
        self.assertEqual(len(game.p1_hand), 6)
        self.assertEqual(game.current_turn, "p2")

    def test_healing_returns_selected_cards_and_removes_empty_groups(self):
        game = make_game()
        game.turn_step = "REGEN_SELECTION"
        game.p1_hand = ["A", "B", "C", "D"]
        game.deck = ["BASE1", "BASE2"]
        game.p1_discard_groups = [
            [{"name": "H1", "is_face_up": True, "owner": "p1"}],
        ]
        game.p2_discard_groups = [
            [{"name": "H2", "is_face_up": False, "owner": "p2"}],
        ]
        game.regen_pool = [
            {
                "owner": "p1",
                "g_idx": 0,
                "item_idx": 0,
                "name": "H1",
                "is_face_up": True,
            },
            {
                "owner": "p2",
                "g_idx": 0,
                "item_idx": 0,
                "name": "H2",
                "is_face_up": False,
            },
        ]
        game.temp_selection = [0, 1]

        with patch(
            "services.game_service.random.shuffle",
            side_effect=lambda cards: None,
        ):
            GameService.confirm_healing(game, "p1", "Alice")

        self.assertEqual(game.p1_discard_groups, [])
        self.assertEqual(game.p2_discard_groups, [])
        self.assertEqual(game.p1_hand[-2:], ["H2", "H1"])
        self.assertEqual(game.temp_selection, [])
        self.assertEqual(game.current_turn, "p2")

    def test_prescience_returns_ordered_cards_then_refills(self):
        game = make_game()
        game.turn_step = "PRESCIENCE_SELECT_1"
        game.p1_hand = ["H1", "H2", "H3", "H4"]
        game.deck = ["BASE"]
        game.prescience_cards = ["A", "B", "C"]

        GameService.choose_prescience_card(game, "p1", 1, "Alice")
        GameService.choose_prescience_card(game, "p1", 1, "Alice")

        self.assertEqual(game.p1_hand[-2:], ["B", "C"])
        self.assertEqual(game.deck, ["BASE", "A"])
        self.assertEqual(game.deck[-1], "A")
        self.assertEqual(game.prescience_cards, [])
        self.assertEqual(game.prescience_ordered, [])

    def test_confirm_prescience_order_applies_all_three_at_once(self):
        game = make_game()
        game.turn_step = "PRESCIENCE_SELECT_1"
        game.p1_hand = ["H1", "H2", "H3", "H4"]
        game.deck = ["BASE"]
        game.prescience_cards = ["A", "B", "C"]

        GameService.confirm_prescience_order(
            game,
            "p1",
            [2, 0, 1],
            "Alice",
        )

        self.assertEqual(game.p1_hand[-2:], ["C", "A"])
        self.assertEqual(game.deck, ["BASE", "B"])
        self.assertEqual(game.deck[-1], "B")
        self.assertEqual(game.prescience_cards, [])
        self.assertEqual(game.prescience_ordered, [])

    def test_mimicked_prescience_draws_all_three_ordered_cards(self):
        game = make_game()
        game.turn_step = "ABILITY"
        game.p1_hand = [
            "カモフラージュ",
            "カモフラージュ",
            "プリサイエンス",
            "H1",
            "H2",
            "H3",
        ]
        game.deck = ["BASE1", "BASE2", "A", "B", "C"]

        GameService.activate_ability(
            game,
            "p1",
            "プリサイエンス",
            "Alice",
            mimic=True,
        )
        self.assertEqual(game.prescience_cards, ["C", "B", "A"])

        GameService.confirm_prescience_order(
            game,
            "p1",
            [1, 2, 0],
            "Alice",
        )

        self.assertEqual(game.p1_hand[-3:], ["B", "A", "C"])
        self.assertEqual(game.deck, ["BASE1", "BASE2"])


class CpuServiceTests(unittest.TestCase):
    def test_easy_cpu_discards_one_card_in_one_step(self):
        game = make_game()
        game.is_cpu = True
        game.cpu_level = "easy"
        game.current_turn = "p2"
        game.turn_step = "DISCARD"
        game.p2_hand = ["A", "B"]

        with patch("services.cpu_service.random.choice", return_value="A"):
            self.assertTrue(CpuService.begin_action(game))
            CpuService.take_step(game)
            CpuService.finish_action(game)

        self.assertEqual(game.p2_hand, ["B"])
        self.assertEqual(game.turn_step, "DRAW")
        self.assertFalse(game.cpu_acting)


if __name__ == "__main__":
    unittest.main()
