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
        self.assertIn("selectedIndices: clairHighlights.hand", renderer)
        self.assertIn("clairHighlights.discards", renderer)
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
