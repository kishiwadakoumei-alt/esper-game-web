import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app


PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_ROOT = PROJECT_ROOT / "frontend"


class FrontendDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.client_context = TestClient(
            create_app(roulette_delay=60, cpu_delay=0)
        )
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)

    def test_root_serves_browser_application(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("text/html")
        )
        self.assertIn('id="landing-screen"', response.text)
        self.assertIn('id="game-screen"', response.text)

    def test_css_and_javascript_are_served_separately(self):
        html = self.client.get("/").text
        css = self.client.get("/static/css/styles.css")
        app_js = self.client.get("/static/js/app.js")
        api_js = self.client.get("/static/js/api.js")
        render_js = self.client.get("/static/js/render.js")

        self.assertNotIn("<style", html)
        self.assertNotIn("<script>", html)
        self.assertIn('href="/static/css/styles.css"', html)
        self.assertIn('src="/static/js/app.js"', html)
        for response in (css, app_js, api_js, render_js):
            self.assertEqual(response.status_code, 200)

    def test_frontend_uses_api_and_public_state_only(self):
        javascript = "\n".join(
            path.read_text()
            for path in sorted(
                (FRONTEND_ROOT / "static" / "js").glob("*.js")
            )
        )

        self.assertIn("/api/rooms/", javascript)
        self.assertIn("/ws/rooms/", javascript)
        self.assertNotIn("game_logic", javascript)
        self.assertNotIn("flet", javascript.lower())

    def test_discard_confirmation_modal_is_separated_from_action(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("discard-dialog", html)
        self.assertIn("discard-card-name", html)
        self.assertIn("discard-card-effect", html)
        self.assertIn("discard-cancel-button", html)
        self.assertIn("discard-confirm-button", html)
        self.assertIn(".discard-dialog", css)
        self.assertIn("CARD_EFFECTS", renderer)
        self.assertIn("confirmDiscard(card, option.index, onAction)", renderer)
        self.assertIn("onAction(\"discard_card\", { index })", renderer)

    def test_ability_confirmation_modal_shows_usage_before_action(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("ability-dialog-name", html)
        self.assertIn("ability-dialog-effect", html)
        self.assertIn("ability-dialog-card-count", html)
        self.assertIn("ability-cancel-button", html)
        self.assertIn("ability-confirm-button", html)
        self.assertIn(".ability-dialog", css)
        self.assertIn("confirmAbility(", renderer)
        self.assertIn("2枚（同名カード2枚）", renderer)
        self.assertIn("3枚（カモフラージュ2枚＋", renderer)
        self.assertIn("onConfirm();", renderer)

    def test_clairvoyance_selection_highlights_opponent_board(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("clairvoyanceHighlights", renderer)
        self.assertIn("option.target.zone === \"opponent_hand\"", renderer)
        self.assertIn(
            "option.target.zone === \"opponent_discard\"",
            renderer,
        )
        self.assertIn("opponentHandHighlights", renderer)
        self.assertIn("...clairHighlights.hand", renderer)
        self.assertIn("...clairHighlights.discards", renderer)
        self.assertIn(".card.hidden-card.selected", css)

    def test_prescience_orders_three_cards_before_confirmation(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("prescience-dialog", html)
        self.assertIn("prescience-order-list", html)
        self.assertIn("prescience-back-button", html)
        self.assertIn("prescience-confirm-button", html)
        self.assertIn(".prescience-option.selected", css)
        self.assertIn("prescienceOrder.splice(selectedPosition, 1)", renderer)
        self.assertIn("prescienceOrder.pop()", renderer)
        self.assertIn("上から${position + 1}枚目", renderer)
        self.assertIn("confirm_prescience_order", renderer)
        self.assertNotIn("select_prescience_card", renderer)

    def test_healing_selection_highlights_each_board_card(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("healingHighlights", renderer)
        self.assertIn("option.target.group_index", renderer)
        self.assertIn("option.target.item_index", renderer)
        self.assertIn("regenHighlights.opponent", renderer)
        self.assertIn("regenHighlights.mine", renderer)
        self.assertIn("selectedCards.has", renderer)
        self.assertIn(".card.selected:not(.hidden-card)", css)
        self.assertIn(".card.hidden-card.selected", css)

    def test_teleport_target_is_confirmed_before_action(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("teleport-dialog", html)
        self.assertIn("teleport-target-name", html)
        self.assertIn("teleport-target-effect", html)
        self.assertIn("teleport-cancel-button", html)
        self.assertIn("teleport-confirm-button", html)
        self.assertIn("捨てさせる", html)
        self.assertIn(".teleport-dialog", css)
        self.assertIn("confirmTeleportTarget(", renderer)
        self.assertIn("select_teleport_target", renderer)
        self.assertIn("onConfirm();", renderer)

    def test_psychokinesis_targets_are_confirmed_from_the_board(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("psychokinesis-dialog", html)
        self.assertIn("psychokinesis-target-label", html)
        self.assertIn("psychokinesis-cancel-button", html)
        self.assertIn("psychokinesis-confirm-button", html)
        self.assertIn("捨てさせる", renderer)
        self.assertIn("戻す", renderer)
        self.assertIn("confirmPsychokinesisTarget(", renderer)
        self.assertIn("bindPsychokinesisBoardTargets", renderer)
        self.assertIn("makeBoardTargetClickable", renderer)
        self.assertIn("psychokinesisHighlights", renderer)
        self.assertIn("psychokinesisSelection = null", renderer)
        self.assertIn("select_psychokinesis_discard", renderer)
        self.assertIn("select_psychokinesis_push", renderer)
        self.assertIn(".psychokinesis-dialog", css)
        self.assertIn(".card.selectable-target", css)
        self.assertIn(".discard-stack.selectable-target", css)

    def test_extra_turn_indicator_has_four_color_levels(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("extra-turn-overlay", html)
        self.assertIn("extra-turn-badge", html)
        for level in range(1, 5):
            self.assertIn(f".extra-turn-level-{level}", css)
        self.assertIn("Math.min(Math.max(count, 1), 4)", renderer)
        self.assertIn("renderExtraTurnIndicators", renderer)
        self.assertIn("EXTRA TURN ×${count}", renderer)
        self.assertIn("タイムリープによる${extraTurnCount}回目", renderer)

    def test_opponent_actions_use_deduplicated_notification_queue(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()
        api = (
            FRONTEND_ROOT / "static" / "js" / "api.js"
        ).read_text()

        self.assertIn("action-event-overlay", html)
        self.assertIn("action-event-title", html)
        self.assertIn("action-event-detail", html)
        self.assertIn("notificationQueue", renderer)
        self.assertIn("event.id > lastActionEventId", renderer)
        self.assertIn("lastActionEventId === null || suppress", renderer)
        self.assertIn("suppressActionEvents: awaitingInitialState", api)
        self.assertIn("event.actor_role !== state.viewer.role", renderer)
        self.assertIn("{ priority: isTimeLeap }", renderer)
        self.assertIn("finishNotification", renderer)
        self.assertIn("YOUR CARDS CHANGED", renderer)
        self.assertIn(".action-event-overlay.tone-normal", css)
        self.assertIn(".action-event-overlay.tone-impact", css)
        self.assertIn("@keyframes action-event-leave", css)
        self.assertIn("pointer-events: none", css)

    def test_turn_changes_are_shown_in_the_notification_queue(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("renderTurnChange(state", renderer)
        self.assertIn("あなたの番です", renderer)
        self.assertIn("相手の番です", renderer)
        self.assertIn("TURN CHANGE", renderer)
        self.assertIn("currentOwner !== lastTurnOwner", renderer)
        self.assertIn("startsAfterDecision", renderer)
        self.assertIn("suppress: suppressActionEvents", renderer)
        self.assertIn(".action-event-overlay.tone-turn-mine", css)
        self.assertIn(".action-event-overlay.tone-turn-opponent", css)

    def test_newly_drawn_cards_are_temporarily_highlighted(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn("updateNewlyDrawnCards(state)", renderer)
        self.assertIn("previousHandCounts", renderer)
        self.assertIn("`${card}:${occurrence}`", renderer)
        self.assertIn("NEW_CARD_HOLD_MS = 3000", renderer)
        self.assertIn("NEW_CARD_FADE_MS = 400", renderer)
        self.assertIn("newly-drawn", renderer)
        self.assertIn(".card.newly-drawn", css)
        self.assertIn("@keyframes newly-drawn-card", css)
        self.assertIn("88.235%", css)
        self.assertIn("resetRenderState()", app)

    def test_battle_log_is_hidden_behind_a_toggle_button(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn("log-toggle-button", html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('aria-controls="log-list"', html)
        self.assertIn("バトルログを見る", html)
        self.assertIn('id="log-list" class="log-list" hidden', html)
        self.assertNotIn('<details class="log-panel" open>', html)
        self.assertIn("setBattleLogOpen", app)
        self.assertIn("バトルログを閉じる", app)
        self.assertIn("logList.hidden", app)
        self.assertIn(".log-toggle-button", css)
        self.assertIn(".log-list[hidden]", css)

    def test_html_css_and_javascript_have_distinct_responsibilities(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        javascript = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn('id="join-form"', html)
        self.assertIn(".landing-grid", css)
        self.assertIn("api.joinRoom", javascript)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("background:", html)


if __name__ == "__main__":
    unittest.main()
