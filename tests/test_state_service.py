import json
import unittest

from game_logic import EsperGame
from services import StateService


def make_game() -> EsperGame:
    game = EsperGame()
    game.players = ["Alice", "Bob"]
    game.current_turn = "p1"
    game.turn_step = "DISCARD"
    game.p1_hand = ["OWN_A", "OWN_B"]
    game.p2_hand = ["SECRET_OPPONENT_A", "SECRET_OPPONENT_B"]
    game.deck = ["SECRET_DECK_A", "SECRET_DECK_B"]
    game.excluded_cards = [
        "SECRET_EXCLUDED_A",
        "SECRET_EXCLUDED_B",
        "SECRET_EXCLUDED_C",
    ]
    game.p1_discard_groups = [
        [{
            "name": "OWN_FACE_DOWN",
            "is_face_up": False,
            "owner": "p1",
        }],
    ]
    game.p2_discard_groups = [
        [{
            "name": "SECRET_OPPONENT_DISCARD",
            "is_face_up": False,
            "owner": "p2",
        }],
        [{
            "name": "PUBLIC_OPPONENT_DISCARD",
            "is_face_up": True,
            "owner": "p2",
        }],
    ]
    game.log_message = "公開ログ"
    game.log_history = []
    game.chat_history = []
    return game


class StateServiceVisibilityTests(unittest.TestCase):
    def test_normal_state_hides_all_opponent_and_deck_secrets(self):
        game = make_game()

        state = StateService.build_public_state(
            game,
            "p1",
            room_id="room",
        )
        encoded = json.dumps(state, ensure_ascii=False)

        self.assertEqual(state["room_id"], "room")
        self.assertEqual(state["opponent"]["hand_count"], 2)
        self.assertIsNone(state["opponent"]["hand"])
        self.assertEqual(state["excluded_cards"], [None, None, None])
        self.assertEqual(
            state["discards"]["mine"][0][0]["name"],
            "OWN_FACE_DOWN",
        )
        self.assertIsNone(
            state["discards"]["opponent"][0][0]["name"]
        )
        self.assertEqual(
            state["discards"]["opponent"][1][0]["name"],
            "PUBLIC_OPPONENT_DISCARD",
        )

        for secret in [
            "SECRET_OPPONENT_A",
            "SECRET_OPPONENT_B",
            "SECRET_DECK_A",
            "SECRET_DECK_B",
            "SECRET_EXCLUDED_A",
            "SECRET_EXCLUDED_B",
            "SECRET_EXCLUDED_C",
            "SECRET_OPPONENT_DISCARD",
        ]:
            self.assertNotIn(secret, encoded)

    def test_finished_state_reveals_opponent_hand_and_excluded_cards(self):
        game = make_game()
        game.turn_step = "GAME_OVER"

        state = StateService.build_public_state(game, "p1")

        self.assertEqual(
            state["opponent"]["hand"],
            ["SECRET_OPPONENT_A", "SECRET_OPPONENT_B"],
        )
        self.assertEqual(
            state["excluded_cards"],
            [
                "SECRET_EXCLUDED_A",
                "SECRET_EXCLUDED_B",
                "SECRET_EXCLUDED_C",
            ],
        )
        self.assertNotIn("SECRET_DECK_A", json.dumps(state))

    def test_each_player_sees_only_their_own_private_hand(self):
        game = make_game()

        p1_state = StateService.build_public_state(game, "p1")
        p2_state = StateService.build_public_state(game, "p2")

        self.assertEqual(p1_state["my_hand"], ["OWN_A", "OWN_B"])
        self.assertEqual(
            p2_state["my_hand"],
            ["SECRET_OPPONENT_A", "SECRET_OPPONENT_B"],
        )
        self.assertIsNone(p1_state["opponent"]["hand"])
        self.assertIsNone(p2_state["opponent"]["hand"])

    def test_invalid_viewer_role_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "viewer_role"):
            StateService.build_public_state(make_game(), "spectator")


class StateServiceInteractionTests(unittest.TestCase):
    def test_prescience_cards_are_visible_only_to_acting_player(self):
        game = make_game()
        game.turn_step = "PRESCIENCE_SELECT_1"
        game.prescience_cards = [
            "SECRET_FUTURE_A",
            "SECRET_FUTURE_B",
            "SECRET_FUTURE_C",
        ]

        actor_state = StateService.build_public_state(game, "p1")
        opponent_state = StateService.build_public_state(game, "p2")

        self.assertIn(
            "confirm_prescience_order",
            actor_state["available_actions"],
        )
        self.assertNotIn(
            "select_prescience_card",
            actor_state["available_actions"],
        )
        self.assertEqual(
            [
                option["card"]
                for option in actor_state["interaction"]["options"]
            ],
            [
                "SECRET_FUTURE_A",
                "SECRET_FUTURE_B",
                "SECRET_FUTURE_C",
            ],
        )
        self.assertIsNone(opponent_state["interaction"])
        opponent_json = json.dumps(opponent_state, ensure_ascii=False)
        self.assertNotIn("SECRET_FUTURE_A", opponent_json)

    def test_clairvoyance_reveals_only_selected_cards_to_actor(self):
        game = make_game()
        game.turn_step = "CLAIR_SELECTION"
        game.clair_pool = [
            {
                "type": "hand",
                "idx": 1,
                "label": "伏せカード 1",
                "name": "SECRET_CLAIR_A",
            },
            {
                "type": "discard",
                "g_idx": 3,
                "label": "伏せカード 2",
                "name": "SECRET_CLAIR_B",
            },
        ]
        game.temp_selection = [0]

        selection_state = StateService.build_public_state(game, "p1")
        self.assertIsNone(
            selection_state["interaction"]["options"][0]["name"]
        )
        self.assertEqual(
            selection_state["interaction"]["options"][0]["target"],
            {"zone": "opponent_hand", "index": 1},
        )
        self.assertEqual(
            selection_state["interaction"]["options"][1]["target"],
            {"zone": "opponent_discard", "index": 3},
        )

        game.turn_step = "CLAIR_REVEAL"
        actor_state = StateService.build_public_state(game, "p1")
        opponent_state = StateService.build_public_state(game, "p2")

        self.assertEqual(
            actor_state["interaction"]["options"][0]["name"],
            "SECRET_CLAIR_A",
        )
        self.assertIsNone(
            actor_state["interaction"]["options"][1]["name"]
        )
        self.assertIsNone(opponent_state["interaction"])
        opponent_json = json.dumps(opponent_state, ensure_ascii=False)
        self.assertNotIn("SECRET_CLAIR_A", opponent_json)
        self.assertNotIn("SECRET_CLAIR_B", opponent_json)

    def test_healing_hides_opponent_face_down_option(self):
        game = make_game()
        game.turn_step = "REGEN_SELECTION"
        game.regen_pool = [
            {
                "owner": "p1",
                "g_idx": 0,
                "item_idx": 1,
                "name": "OWN_HEALING_CARD",
                "is_face_up": False,
            },
            {
                "owner": "p2",
                "g_idx": 2,
                "item_idx": 0,
                "name": "SECRET_HEALING_CARD",
                "is_face_up": False,
            },
            {
                "owner": "p2",
                "g_idx": 3,
                "item_idx": 1,
                "name": "PUBLIC_HEALING_CARD",
                "is_face_up": True,
            },
        ]
        game.temp_selection = [0, 1, 2]

        state = StateService.build_public_state(game, "p1")
        options = state["interaction"]["options"]

        self.assertEqual(options[0]["name"], "OWN_HEALING_CARD")
        self.assertIsNone(options[1]["name"])
        self.assertEqual(options[2]["name"], "PUBLIC_HEALING_CARD")
        self.assertEqual(
            options[0]["target"],
            {"zone": "mine", "group_index": 0, "item_index": 1},
        )
        self.assertEqual(
            options[1]["target"],
            {
                "zone": "opponent",
                "group_index": 2,
                "item_index": 0,
            },
        )
        self.assertTrue(all(option["selected"] for option in options))
        self.assertNotIn(
            "SECRET_HEALING_CARD",
            json.dumps(state, ensure_ascii=False),
        )

    def test_psychokinesis_options_do_not_contain_card_names(self):
        game = make_game()
        game.turn_step = "PSY_DISCARD_SELECTION"

        state = StateService.build_public_state(game, "p1")
        options = state["interaction"]["options"]

        self.assertEqual(
            options,
            [
                {"index": 0, "label": "伏せカード 1"},
                {"index": 1, "label": "伏せカード 2"},
            ],
        )
        encoded = json.dumps(state, ensure_ascii=False)
        self.assertNotIn("SECRET_OPPONENT_A", encoded)
        self.assertNotIn("SECRET_OPPONENT_B", encoded)


class StateServiceActionTests(unittest.TestCase):
    def test_actions_are_limited_by_turn_and_step(self):
        game = make_game()

        p1_state = StateService.build_public_state(game, "p1")
        p2_state = StateService.build_public_state(game, "p2")

        self.assertEqual(
            p1_state["available_actions"],
            ["discard_card"],
        )
        self.assertEqual(p2_state["available_actions"], [])
        self.assertEqual(p1_state["interaction"]["kind"], "discard")
        self.assertIsNone(p2_state["interaction"])

    def test_waiting_state_has_no_actions_even_with_esper_hand(self):
        game = make_game()
        game.turn_step = "WAITING"
        game.p1_hand = ["A"] * 5

        state = StateService.build_public_state(game, "p1")

        self.assertEqual(state["available_actions"], [])
        self.assertIsNone(state["interaction"])

    def test_esper_can_be_declared_outside_viewers_turn(self):
        game = make_game()
        game.current_turn = "p2"
        game.p1_hand = ["A"] * 5

        state = StateService.build_public_state(game, "p1")

        self.assertEqual(state["available_actions"], ["declare_esper"])

    def test_ability_state_includes_only_usable_options(self):
        game = make_game()
        game.turn_step = "ABILITY"
        game.p1_hand = [
            "タイムリープ",
            "タイムリープ",
            "カモフラージュ",
            "カモフラージュ",
            "ヒーリング",
            "OTHER",
        ]
        game.deck = ["ONE", "TWO"]

        state = StateService.build_public_state(game, "p1")
        actions = state["available_actions"]
        interaction = state["interaction"]

        self.assertIn("activate_ability", actions)
        self.assertIn("open_mimic_selection", actions)
        self.assertEqual(
            [item["card"] for item in interaction["abilities"]],
            ["タイムリープ"],
        )
        mimic_by_card = {
            item["card"]: item for item in interaction["mimic_targets"]
        }
        self.assertTrue(mimic_by_card["タイムリープ"]["disabled"])
        self.assertFalse(mimic_by_card["ヒーリング"]["disabled"])

    def test_disabled_ability_options_are_not_exposed_as_actions(self):
        game = make_game()
        game.turn_step = "ABILITY"
        game.p1_hand = [
            "タイムリープ",
            "タイムリープ",
            "カモフラージュ",
            "カモフラージュ",
            "プリサイエンス",
        ]
        game.deck = ["ONE"]

        state = StateService.build_public_state(game, "p1")

        self.assertNotIn("activate_ability", state["available_actions"])
        self.assertNotIn(
            "open_mimic_selection",
            state["available_actions"],
        )

    def test_finished_state_exposes_only_rematch_and_leave_actions(self):
        game = make_game()
        game.turn_step = "GAME_OVER"

        state = StateService.build_public_state(game, "p1")

        self.assertEqual(
            state["available_actions"],
            ["request_rematch", "leave_room"],
        )
        self.assertIsNone(state["interaction"])


if __name__ == "__main__":
    unittest.main()
