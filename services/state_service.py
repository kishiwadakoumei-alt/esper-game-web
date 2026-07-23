"""閲覧者ごとに秘匿情報を除いたゲーム状態を生成するサービス。"""

from collections import Counter
from typing import Any

from game_logic import EsperGame
from schemas import PublicGameState
from services.game_service import NAME_MAP


class StateService:
    """EsperGameをブラウザへ公開可能なJSON互換辞書へ変換する。"""

    FINAL_STEPS = {"GAME_CLEAR", "GAME_OVER"}

    @classmethod
    def build_public_state(
        cls,
        game: EsperGame,
        viewer_role: str,
        *,
        room_id: str | None = None,
    ) -> PublicGameState:
        cls._validate_role(viewer_role)
        opponent_role = game.get_op_role(viewer_role)
        viewer_hand = game.get_hand(viewer_role)
        opponent_hand = game.get_hand(opponent_role)
        is_finished = game.turn_step in cls.FINAL_STEPS

        state: dict[str, Any] = {
            "version": 1,
            "room_id": room_id,
            "viewer": {
                "role": viewer_role,
                "name": game.get_player_name(viewer_role),
            },
            "game": {
                "turn_step": game.turn_step,
                "current_turn": game.current_turn,
                "is_my_turn": game.current_turn == viewer_role,
                "is_cpu": game.is_cpu,
                "deck_count": len(game.deck),
                "extra_turn_chain": game.extra_turn_chain,
                "latest_log": game.log_message,
                "finished": is_finished,
            },
            "opponent": {
                "role": opponent_role,
                "name": game.get_player_name(opponent_role),
                "hand_count": len(opponent_hand),
                "hand": (
                    game.sort_hand(opponent_hand)
                    if is_finished
                    else None
                ),
            },
            "my_hand": game.sort_hand(viewer_hand),
            "discards": {
                "mine": cls._serialize_discard_groups(
                    game.get_discard_groups(viewer_role),
                    viewer_role,
                ),
                "opponent": cls._serialize_discard_groups(
                    game.get_discard_groups(opponent_role),
                    viewer_role,
                ),
            },
            "excluded_cards": (
                list(game.excluded_cards)
                if is_finished
                else [None] * len(game.excluded_cards)
            ),
            "available_actions": cls._available_actions(
                game,
                viewer_role,
            ),
            "interaction": cls._interaction(game, viewer_role),
            "logs": [dict(entry) for entry in game.log_history],
            "action_events": cls._action_events(game, viewer_role),
            "chat": list(game.chat_history),
            "rematch": {
                "requested_by_me": viewer_role in game.rematch_requests,
                "requested_by_opponent": (
                    opponent_role in game.rematch_requests
                ),
            },
        }
        return state

    @staticmethod
    def _action_events(
        game: EsperGame,
        viewer_role: str,
    ) -> list[dict[str, Any]]:
        events = []
        for event in game.action_events:
            message = event["messages"][viewer_role]
            actor_role = event["actor_role"]
            actor_name = game.get_player_name(actor_role)
            actor_label = "あなた" if actor_role == viewer_role else "相手"
            title = message["title"].replace(
                actor_name,
                actor_label,
                1,
            )
            events.append({
                "id": event["id"],
                "actor_role": actor_role,
                "kind": event["kind"],
                "title": title,
                "detail": message["detail"],
                "tone": message["tone"],
                "duration_ms": event["duration_ms"],
            })
        return events

    @classmethod
    def _available_actions(
        cls,
        game: EsperGame,
        viewer_role: str,
    ) -> list[str]:
        actions = []
        if game.turn_step in {
            "WAITING",
            "DECIDING_TURN",
            "ROOM_DISBANDED",
        }:
            return actions

        if game.turn_step in cls.FINAL_STEPS:
            if viewer_role not in game.rematch_requests:
                actions.append("request_rematch")
            actions.append("leave_room")
            return actions

        if game.check_esper(game.get_hand(viewer_role)):
            actions.append("declare_esper")

        if game.current_turn != viewer_role:
            return actions

        actions_by_step = {
            "DISCARD": ["discard_card"],
            "DRAW": ["draw_hand"],
            "THINK": ["open_ability_selection", "pass_turn"],
            "ABILITY": ["cancel_ability_selection"],
            "MIMIC_SELECTION": ["cancel_mimic_selection"],
            "TELEPORT_SELECTION": ["select_teleport_target"],
            "PSY_DISCARD_SELECTION": ["select_psychokinesis_discard"],
            "PSY_PUSH_SELECTION": ["select_psychokinesis_push"],
            "REGEN_SELECTION": [
                "toggle_healing_selection",
                "confirm_healing",
            ],
            "CLAIR_SELECTION": [
                "toggle_clairvoyance_selection",
                "confirm_clairvoyance",
            ],
            "CLAIR_REVEAL": ["finish_clairvoyance"],
            "PRESCIENCE_SELECT_1": ["confirm_prescience_order"],
            "PRESCIENCE_SELECT_2": ["confirm_prescience_order"],
        }
        actions.extend(actions_by_step.get(game.turn_step, []))

        if game.turn_step == "ABILITY":
            interaction = cls._ability_interaction(game, viewer_role)
            if any(
                not ability["disabled"]
                for ability in interaction["abilities"]
            ):
                actions.append("activate_ability")
            if any(
                not target["disabled"]
                for target in interaction["mimic_targets"]
            ):
                actions.append("open_mimic_selection")
        elif game.turn_step == "MIMIC_SELECTION":
            interaction = cls._mimic_interaction(game, viewer_role)
            if any(
                not target["disabled"]
                for target in interaction["targets"]
            ):
                actions.append("activate_mimic")

        return actions

    @classmethod
    def _interaction(
        cls,
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any] | None:
        if game.current_turn != viewer_role:
            return None

        step = game.turn_step
        if step == "DISCARD":
            return {
                "kind": "discard",
                "options": [
                    {
                        "index": index,
                        "card": card,
                    }
                    for index, card in enumerate(
                        game.sort_hand(game.get_hand(viewer_role))
                    )
                ],
            }
        if step == "ABILITY":
            return cls._ability_interaction(game, viewer_role)
        if step == "MIMIC_SELECTION":
            return cls._mimic_interaction(game, viewer_role)
        if step == "TELEPORT_SELECTION":
            return {
                "kind": "teleport",
                "options": [
                    {
                        "card": card,
                        "label": NAME_MAP.get(card, card),
                    }
                    for card in game.types
                ],
            }
        if step == "PSY_DISCARD_SELECTION":
            return cls._psychokinesis_discard_interaction(
                game,
                viewer_role,
            )
        if step == "PSY_PUSH_SELECTION":
            return cls._psychokinesis_push_interaction(
                game,
                viewer_role,
            )
        if step == "REGEN_SELECTION":
            return cls._healing_interaction(game, viewer_role)
        if step in {"CLAIR_SELECTION", "CLAIR_REVEAL"}:
            return cls._clairvoyance_interaction(game)
        if step in {"PRESCIENCE_SELECT_1", "PRESCIENCE_SELECT_2"}:
            return cls._prescience_interaction(game)
        return None

    @staticmethod
    def _ability_interaction(
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any]:
        hand = game.get_hand(viewer_role)
        counts = Counter(hand)
        deck_count = len(game.deck)
        abilities = []
        for card, count in counts.items():
            if count < 2 or card == "カモフラージュ":
                continue
            disabled = deck_count <= 1 and card != "ヒーリング"
            abilities.append({
                "card": card,
                "label": NAME_MAP.get(card, card),
                "disabled": disabled,
            })

        mimic_targets = StateService._mimic_targets(game, viewer_role)
        return {
            "kind": "ability",
            "abilities": abilities,
            "mimic_targets": mimic_targets,
        }

    @staticmethod
    def _mimic_interaction(
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any]:
        return {
            "kind": "mimic",
            "targets": StateService._mimic_targets(game, viewer_role),
        }

    @staticmethod
    def _mimic_targets(
        game: EsperGame,
        viewer_role: str,
    ) -> list[dict[str, Any]]:
        hand = game.get_hand(viewer_role)
        if hand.count("カモフラージュ") < 2:
            return []

        deck_count = len(game.deck)
        return [
            {
                "card": card,
                "label": NAME_MAP.get(card, card),
                "disabled": (
                    deck_count <= 2 and card != "ヒーリング"
                ),
            }
            for card in sorted(set(hand))
            if card != "カモフラージュ"
        ]

    @staticmethod
    def _psychokinesis_discard_interaction(
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any]:
        opponent_hand_count = len(
            game.get_hand(game.get_op_role(viewer_role))
        )
        return {
            "kind": "psychokinesis_discard",
            "options": [
                {
                    "index": index,
                    "label": f"伏せカード {index + 1}",
                }
                for index in range(opponent_hand_count)
            ],
        }

    @staticmethod
    def _psychokinesis_push_interaction(
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any]:
        opponent_role = game.get_op_role(viewer_role)
        options = []
        for group_index, group in enumerate(
            game.get_discard_groups(opponent_role)
        ):
            if len(group) == 1 and not group[0]["is_face_up"]:
                options.append({
                    "group_index": group_index,
                    "label": f"裏向きの捨て札 {len(options) + 1}",
                })
        return {
            "kind": "psychokinesis_push",
            "options": options,
        }

    @staticmethod
    def _healing_interaction(
        game: EsperGame,
        viewer_role: str,
    ) -> dict[str, Any]:
        options = []
        for index, item in enumerate(game.regen_pool):
            is_mine = item["owner"] == viewer_role
            visible = item["is_face_up"] or is_mine
            target = None
            if "g_idx" in item and "item_idx" in item:
                target = {
                    "zone": "mine" if is_mine else "opponent",
                    "group_index": item["g_idx"],
                    "item_index": item["item_idx"],
                }
            options.append({
                "index": index,
                "owner": item["owner"],
                "name": item["name"] if visible else None,
                "is_face_up": item["is_face_up"],
                "selected": index in game.temp_selection,
                "target": target,
            })
        return {
            "kind": "healing",
            "maximum": 3,
            "selected_count": len(game.temp_selection),
            "options": options,
        }

    @staticmethod
    def _clairvoyance_interaction(
        game: EsperGame,
    ) -> dict[str, Any]:
        options = []
        reveal = game.turn_step == "CLAIR_REVEAL"
        for index, item in enumerate(game.clair_pool):
            selected = index in game.temp_selection
            target = None
            if item.get("type") == "hand":
                target = {
                    "zone": "opponent_hand",
                    "index": item["idx"],
                }
            elif item.get("type") == "discard":
                target = {
                    "zone": "opponent_discard",
                    "index": item["g_idx"],
                }
            options.append({
                "index": index,
                "label": item["label"],
                "selected": selected,
                "name": item["name"] if reveal and selected else None,
                "target": target,
            })
        return {
            "kind": "clairvoyance_reveal" if reveal else "clairvoyance",
            "maximum": 2,
            "selected_count": len(game.temp_selection),
            "options": options,
        }

    @staticmethod
    def _prescience_interaction(game: EsperGame) -> dict[str, Any]:
        position = (
            1 if game.turn_step == "PRESCIENCE_SELECT_1" else 2
        )
        return {
            "kind": "prescience",
            "position": position,
            "ordered": list(game.prescience_ordered),
            "options": [
                {
                    "index": index,
                    "card": card,
                }
                for index, card in enumerate(game.prescience_cards)
            ],
        }

    @staticmethod
    def _serialize_discard_groups(
        groups: list[list[dict]],
        viewer_role: str,
    ) -> list[list[dict[str, Any]]]:
        serialized = []
        for group in groups:
            serialized.append([
                {
                    "name": (
                        card["name"]
                        if card["is_face_up"]
                        or card["owner"] == viewer_role
                        else None
                    ),
                    "is_face_up": card["is_face_up"],
                    "owner": card["owner"],
                }
                for card in group
            ])
        return serialized

    @staticmethod
    def _validate_role(viewer_role: str) -> None:
        if viewer_role not in {"p1", "p2"}:
            raise ValueError("viewer_role must be 'p1' or 'p2'")
