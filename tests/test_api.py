import json
import time
import unittest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.main import create_app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(roulette_delay=60, cpu_delay=0)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    @staticmethod
    def _headers(token):
        return {"Authorization": f"Bearer {token}"}

    def _join(self, room_id, name):
        response = self.client.post(
            "/api/rooms/join",
            json={"room_id": room_id, "name": name},
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_health(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_cpu_room_ids_do_not_collide(self):
        first = self.client.post(
            "/api/rooms/cpu",
            json={"name": "Alice", "level": "easy"},
        ).json()
        second = self.client.post(
            "/api/rooms/cpu",
            json={"name": "Bob", "level": "easy"},
        ).json()

        self.assertNotEqual(first["room_id"], second["room_id"])
        self.assertIn(first["room_id"], self.app.state.context.rooms)
        self.assertIn(second["room_id"], self.app.state.context.rooms)

    def test_join_assigns_roles_and_rejects_third_player(self):
        first = self._join("join-room", "Alice")
        second = self._join("join-room", "Bob")
        third = self.client.post(
            "/api/rooms/join",
            json={"room_id": "join-room", "name": "Carol"},
        )

        self.assertEqual(first["role"], "p1")
        self.assertEqual(second["role"], "p2")
        self.assertNotEqual(first["token"], second["token"])
        self.assertEqual(third.status_code, 409)

    def test_state_requires_matching_bearer_session(self):
        first = self._join("room-a", "Alice")
        second = self._join("room-b", "Bob")

        missing = self.client.get("/api/rooms/room-a/state")
        wrong_room = self.client.get(
            "/api/rooms/room-a/state",
            headers=self._headers(second["token"]),
        )
        valid = self.client.get(
            "/api/rooms/room-a/state",
            headers=self._headers(first["token"]),
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong_room.status_code, 403)
        self.assertEqual(valid.status_code, 200)

    def test_opponent_hand_is_not_exposed(self):
        first = self._join("secret-room", "Alice")
        game = self.app.state.context.rooms["secret-room"]
        game.p2_hand = ["DO_NOT_EXPOSE"]

        response = self.client.get(
            "/api/rooms/secret-room/state",
            headers=self._headers(first["token"]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("DO_NOT_EXPOSE", json.dumps(response.json()))
        self.assertEqual(response.json()["opponent"]["hand_count"], 1)
        self.assertIsNone(response.json()["opponent"]["hand"])

    def test_action_revalidates_turn_and_payload(self):
        first = self._join("action-room", "Alice")
        second = self._join("action-room", "Bob")
        game = self.app.state.context.rooms["action-room"]
        game.current_turn = "p1"
        game.turn_step = "DISCARD"
        game.p1_hand = ["A", "B", "C", "D", "E", "F"]
        game.deck = ["G"]

        wrong_player = self.client.post(
            "/api/rooms/action-room/actions",
            headers=self._headers(second["token"]),
            json={"action": "discard_card", "payload": {"index": 0}},
        )
        invalid_index = self.client.post(
            "/api/rooms/action-room/actions",
            headers=self._headers(first["token"]),
            json={"action": "discard_card", "payload": {"index": 99}},
        )
        valid = self.client.post(
            "/api/rooms/action-room/actions",
            headers=self._headers(first["token"]),
            json={"action": "discard_card", "payload": {"index": 0}},
        )

        self.assertEqual(wrong_player.status_code, 409)
        self.assertEqual(invalid_index.status_code, 422)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(game.turn_step, "DRAW")
        self.assertEqual(len(game.p1_hand), 5)

    def test_websocket_gets_initial_state_chat_update_and_pong(self):
        first = self._join("ws-room", "Alice")
        token = first["token"]

        with self.client.websocket_connect(
            f"/ws/rooms/ws-room?token={token}"
        ) as websocket:
            initial = websocket.receive_json()
            self.assertEqual(initial["type"], "state")
            self.assertEqual(initial["data"]["viewer"]["role"], "p1")

            response = self.client.post(
                "/api/rooms/ws-room/chat",
                headers=self._headers(token),
                json={"message": "hello"},
            )
            self.assertEqual(response.status_code, 200)
            update = websocket.receive_json()
            self.assertEqual(
                update["data"]["chat"][-1],
                "💬 Alice: hello",
            )

            websocket.send_json({"type": "ping"})
            self.assertEqual(
                websocket.receive_json(),
                {"type": "pong"},
            )

    def test_websocket_rejects_invalid_session(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect(
                "/ws/rooms/unknown?token=invalid"
            ):
                pass

    def test_roulette_runs_as_background_task(self):
        app = create_app(roulette_delay=0, cpu_delay=0)
        with TestClient(app) as client:
            client.post(
                "/api/rooms/join",
                json={"room_id": "roulette", "name": "Alice"},
            )
            second = client.post(
                "/api/rooms/join",
                json={"room_id": "roulette", "name": "Bob"},
            ).json()

            for _ in range(100):
                response = client.get(
                    "/api/rooms/roulette/state",
                    headers=self._headers(second["token"]),
                )
                if response.json()["game"]["turn_step"] != "DECIDING_TURN":
                    break
                time.sleep(0.001)

            self.assertEqual(
                response.json()["game"]["turn_step"],
                "DISCARD",
            )

    def test_cpu_rematch_is_accepted_when_human_ends_game(self):
        response = self.client.post(
            "/api/rooms/cpu",
            json={"name": "Alice", "level": "easy"},
        )
        self.assertEqual(response.status_code, 200)
        session = response.json()
        game = self.app.state.context.rooms[session["room_id"]]
        game.current_turn = "p1"
        game.turn_step = "DISCARD"
        game.p1_hand = ["A", "A", "A", "A", "A", "B"]

        result = self.client.post(
            f"/api/rooms/{session['room_id']}/actions",
            headers=self._headers(session["token"]),
            json={"action": "declare_esper"},
        )

        self.assertEqual(result.status_code, 200)
        self.assertEqual(game.turn_step, "GAME_CLEAR")
        self.assertIn("p2", game.rematch_requests)
        self.assertTrue(result.json()["rematch"]["requested_by_opponent"])

    def test_cpu_turn_progresses_in_background(self):
        app = create_app(roulette_delay=60, cpu_delay=0)
        with TestClient(app) as client:
            session = client.post(
                "/api/rooms/cpu",
                json={"name": "Alice", "level": "easy"},
            ).json()
            game = app.state.context.rooms[session["room_id"]]
            game.current_turn = "p1"
            game.turn_step = "THINK"

            response = client.post(
                f"/api/rooms/{session['room_id']}/actions",
                headers=self._headers(session["token"]),
                json={"action": "pass_turn"},
            )
            self.assertEqual(response.status_code, 200)

            for _ in range(100):
                state = client.get(
                    f"/api/rooms/{session['room_id']}/state",
                    headers=self._headers(session["token"]),
                ).json()
                if (
                    state["game"]["current_turn"] == "p1"
                    and state["game"]["turn_step"] == "DISCARD"
                ):
                    break
                time.sleep(0.001)

            self.assertEqual(state["game"]["current_turn"], "p1")
            self.assertEqual(state["game"]["turn_step"], "DISCARD")
            self.assertEqual(len(game.p2_discard_groups), 1)


if __name__ == "__main__":
    unittest.main()
