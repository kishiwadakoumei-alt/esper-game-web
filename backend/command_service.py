"""HTTPで受け取った操作を検証し、ゲームサービスへ振り分ける。"""

from typing import Any

from fastapi import HTTPException, status

from game_logic import EsperGame
from services import GameService, StateService

from .session_store import PlayerSession


class CommandService:
    """公開状態に示された操作だけを実行する。"""

    @classmethod
    def execute(
        cls,
        game: EsperGame,
        session: PlayerSession,
        action: str,
        payload: dict[str, Any],
    ) -> None:
        public_state = StateService.build_public_state(
            game,
            session.role,
            room_id=session.room_id,
        )
        if action not in public_state["available_actions"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="現在の状態では実行できない操作です",
            )

        role = session.role
        name = session.player_name
        interaction = public_state["interaction"]

        if action == "declare_esper":
            GameService.declare_esper(game, role, name)
        elif action == "discard_card":
            option = cls._option_by_index(interaction, payload)
            GameService.discard_card(game, role, option["card"], name)
        elif action == "draw_hand":
            GameService.draw_hand(game, role, name)
        elif action == "open_ability_selection":
            GameService.open_ability_selection(game)
        elif action == "pass_turn":
            GameService.pass_turn(game, role, name)
        elif action == "cancel_ability_selection":
            GameService.cancel_ability_selection(game)
        elif action == "activate_ability":
            card = cls._enabled_card(
                interaction["abilities"],
                payload,
            )
            GameService.activate_ability(game, role, card, name)
        elif action == "open_mimic_selection":
            GameService.open_mimic_selection(game)
        elif action == "cancel_mimic_selection":
            GameService.cancel_mimic_selection(game)
        elif action == "activate_mimic":
            card = cls._enabled_card(
                interaction["targets"],
                payload,
            )
            GameService.activate_ability(
                game,
                role,
                card,
                name,
                mimic=True,
            )
        elif action == "select_teleport_target":
            card = cls._card_option(interaction["options"], payload)
            GameService.teleport(game, role, card, name)
        elif action == "select_psychokinesis_discard":
            option = cls._option_by_index(interaction, payload)
            opponent_hand = game.sort_hand(
                game.get_hand(game.get_op_role(role))
            )
            GameService.psychokinesis_discard(
                game,
                role,
                opponent_hand[option["index"]],
                name,
            )
        elif action == "select_psychokinesis_push":
            group_index = cls._group_option(
                interaction["options"],
                payload,
            )
            GameService.psychokinesis_push(
                game,
                role,
                group_index,
                name,
            )
        elif action == "toggle_healing_selection":
            option = cls._option_by_index(interaction, payload)
            GameService.toggle_healing_selection(
                game,
                option["index"],
            )
        elif action == "confirm_healing":
            GameService.confirm_healing(game, role, name)
        elif action == "toggle_clairvoyance_selection":
            option = cls._option_by_index(interaction, payload)
            GameService.toggle_clairvoyance_selection(
                game,
                option["index"],
            )
        elif action == "confirm_clairvoyance":
            GameService.confirm_clairvoyance(game)
        elif action == "finish_clairvoyance":
            GameService.finish_clairvoyance(game, role, name)
        elif action == "confirm_prescience_order":
            ordered_indices = cls._prescience_order(interaction, payload)
            GameService.confirm_prescience_order(
                game,
                role,
                ordered_indices,
                name,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="未対応の操作です",
            )

    @staticmethod
    def _prescience_order(
        interaction: dict[str, Any],
        payload: dict[str, Any],
    ) -> list[int]:
        order = payload.get("order")
        valid_indices = [
            option["index"] for option in interaction["options"]
        ]
        if (
            not isinstance(order, list)
            or any(
                isinstance(index, bool) or not isinstance(index, int)
                for index in order
            )
            or len(order) != len(valid_indices)
            or sorted(order) != sorted(valid_indices)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="orderには全カードのindexを重複なく指定してください",
            )
        return order

    @staticmethod
    def _payload_index(payload: dict[str, Any]) -> int:
        index = payload.get("index")
        if isinstance(index, bool) or not isinstance(index, int):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="indexには整数を指定してください",
            )
        return index

    @classmethod
    def _option_by_index(
        cls,
        interaction: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        index = cls._payload_index(payload)
        for option in interaction["options"]:
            if option["index"] == index:
                return option
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="選択肢に存在しないindexです",
        )

    @staticmethod
    def _payload_card(payload: dict[str, Any]) -> str:
        card = payload.get("card")
        if not isinstance(card, str) or not card:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="cardを指定してください",
            )
        return card

    @classmethod
    def _enabled_card(
        cls,
        options: list[dict[str, Any]],
        payload: dict[str, Any],
    ) -> str:
        card = cls._payload_card(payload)
        for option in options:
            if option["card"] == card and not option["disabled"]:
                return card
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="発動できないカードです",
        )

    @classmethod
    def _card_option(
        cls,
        options: list[dict[str, Any]],
        payload: dict[str, Any],
    ) -> str:
        card = cls._payload_card(payload)
        if any(option["card"] == card for option in options):
            return card
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="選択肢に存在しないカードです",
        )

    @classmethod
    def _group_option(
        cls,
        options: list[dict[str, Any]],
        payload: dict[str, Any],
    ) -> int:
        group_index = payload.get("group_index")
        if (
            isinstance(group_index, bool)
            or not isinstance(group_index, int)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="group_indexには整数を指定してください",
            )
        if any(
            option["group_index"] == group_index
            for option in options
        ):
            return group_index
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="選択肢に存在しないgroup_indexです",
        )
