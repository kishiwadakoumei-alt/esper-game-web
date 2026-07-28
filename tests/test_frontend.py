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
        self.assertIn(
            '<p class="eyebrow">超能力カードゲーム</p>',
            response.text,
        )
        self.assertIn(
            '<h1><em>ESPER</em></h1>',
            response.text,
        )

    def test_room_invitation_url_prefills_room_and_can_be_shared(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        for element_id in (
            "invite-banner",
            "invite-room-code",
            "join-room-button",
            "share-room-button",
        ):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn("URLSearchParams(window.location.search)", app)
        self.assertIn('.get("room")', app)
        self.assertIn("applyRoomInvitation", app)
        self.assertIn('url.searchParams.set("room", roomId)', app)
        self.assertIn('const roomId = roomInput.value.trim()', app)
        self.assertIn("共有するあいことばを入力してください。", app)
        self.assertNotIn('url.searchParams.set("token"', app)
        self.assertIn('typeof navigator.share === "function"', app)
        self.assertIn("navigator.clipboard.writeText(url)", app)
        self.assertIn("この部屋に参加する", app)
        self.assertIn(".invite-banner", css)
        self.assertIn(".entry-share-button", css)

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

    def test_fastapi_entrypoint_replaces_flet_runtime(self):
        requirements = (PROJECT_ROOT / "requirements.txt").read_text()
        entrypoint = (PROJECT_ROOT / "main.py").read_text()

        self.assertFalse((PROJECT_ROOT / "ui_views.py").exists())
        self.assertNotIn("flet", requirements.lower().splitlines())
        self.assertNotIn("flet", entrypoint.lower())
        self.assertIn("from backend.main import app", entrypoint)
        self.assertIn("os.environ.get(\"PORT\", \"8000\")", entrypoint)

    def test_rules_dialog_explains_setup_turns_and_win_conditions(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        self.assertIn("遊び方・能力一覧", html)
        self.assertIn("basic-rules-title", html)
        self.assertIn("turn-rules-title", html)
        self.assertIn("同じ能力カードを5枚以上", html)
        self.assertIn("手札6枚から開始", html)
        self.assertIn("相手のターンでも宣言可能", html)
        self.assertIn("カードを1枚捨てる", html)
        self.assertIn("山札から引く", html)
        self.assertIn("能力を使うか決める", html)
        self.assertIn("伏せ札", html)
        self.assertIn("捨て札が18組", html)
        self.assertIn("カモフラージュのESPER判定", html)
        self.assertIn("7つの能力", html)
        self.assertIn(".game-rules", css)
        self.assertIn(".rule-summary-grid", css)
        self.assertIn(".turn-rules", css)
        self.assertIn(".rule-detail-grid", css)
        self.assertIn("overflow-y: auto", css)

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
        self.assertIn("bindClairvoyanceBoardTargets", renderer)
        self.assertIn("toggle_clairvoyance_selection", renderer)
        self.assertIn("透視対象に選択", renderer)
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
        self.assertIn("prescience-selection-hand-preview", html)
        self.assertIn("prescience-selection-hand", html)
        self.assertIn("prescience-confirm-hand", html)
        self.assertIn("prescience-back-button", html)
        self.assertIn("prescience-confirm-button", html)
        self.assertIn(".prescience-option.selected", css)
        self.assertIn(".prescience-hand-preview", css)
        self.assertIn(".prescience-hand-row", css)
        self.assertIn("repeat(6, minmax(0, 1fr))", css)
        self.assertIn("repeat(3, minmax(0, 1fr))", css)
        self.assertIn("renderPrescienceHandPreview", renderer)
        self.assertIn('"prescience-selection-hand", state.my_hand', renderer)
        self.assertIn('"prescience-confirm-hand", state.my_hand', renderer)
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
        self.assertIn("bindHealingBoardTargets", renderer)
        self.assertIn("toggle_healing_selection", renderer)
        self.assertIn("option.target.zone === \"mine\"", renderer)
        self.assertIn(".card.selected:not(.hidden-card)", css)
        self.assertIn(".card.hidden-card.selected", css)

    def test_healing_targets_are_confirmed_in_a_modal(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("healing-confirm-dialog", html)
        self.assertIn("healing-confirm-list", html)
        self.assertIn("healing-confirm-back-button", html)
        self.assertIn("healing-confirm-button", html)
        self.assertIn("confirmHealingSelection", renderer)
        self.assertIn('handlers.action("confirm_healing")', renderer)
        self.assertIn("option.selected", renderer)
        self.assertIn('option.name || "裏向きのカード"', renderer)
        self.assertIn(".healing-confirm-dialog", css)
        self.assertIn(".healing-confirm-list", css)

    def test_stacked_discards_expand_before_card_selection(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("expandedDiscardStacks", renderer)
        self.assertIn("applyDiscardStackLayout", renderer)
        self.assertIn("group.length > 1", renderer)
        self.assertIn('stack.addEventListener("click", expand, true)', renderer)
        self.assertIn("event.stopPropagation()", renderer)
        self.assertIn("discard-stack-toggle", renderer)
        self.assertIn('expanded ? "−" : "＋"', renderer)
        self.assertIn("expandedDiscardStacks.delete(stackKey)", renderer)
        self.assertIn('querySelectorAll(":scope > .card")', renderer)
        self.assertIn("expandedDiscardStacks.clear()", renderer)
        self.assertIn(".discard-stack.expanded", css)
        self.assertIn(".discard-stack.expandable:not(.expanded)", css)
        self.assertIn(".discard-stack-toggle", css)
        self.assertIn("position: relative", css)

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

    def test_action_panel_is_replaced_by_contextual_controls(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertNotIn("class=\"action-panel\"", html)
        self.assertNotIn("action-content", html)
        self.assertNotIn(".action-panel", css)
        self.assertIn("context-action-bar", html)
        self.assertIn("choice-dialog", html)
        self.assertIn("deck-action-button", html)
        self.assertIn("renderActionBar", renderer)
        self.assertIn("renderChoiceDialog", renderer)
        self.assertIn("bindDeckAction", renderer)
        self.assertNotIn("renderSelectionOptions", renderer)

    def test_private_face_down_discards_stay_hidden_and_can_be_revealed(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("discard-reveal-dialog", html)
        self.assertIn("discard-reveal-name", html)
        self.assertIn("discard-reveal-effect", html)
        self.assertIn("hidden: !card.is_face_up", renderer)
        self.assertIn("bindOwnDiscardReveal", renderer)
        self.assertIn("showDiscardReveal(card.name)", renderer)
        self.assertIn("state.game.turn_step === \"REGEN_SELECTION\"", renderer)
        self.assertIn(".card.revealable-card", css)

    def test_finished_game_gets_outcome_specific_cinematic_overlay(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        for element_id in (
            "victory-overlay",
            "victory-sigil-icon",
            "victory-kicker",
            "victory-title",
            "victory-copy",
            "victory-card-fan",
            "opponent-result-card-fan",
            "victory-dominant-label",
            "result-condition-label",
            "victory-reason",
            "my-result-status",
            "opponent-result-status",
            "victory-rematch-button",
            "victory-result-button",
            "victory-leave-button",
        ):
            self.assertIn(f'id="{element_id}"', html)

        self.assertIn("RESULT_PRESENTATIONS", renderer)
        self.assertIn("ESPER ACHIEVED", renderer)
        self.assertIn("PSYCHIC LINK LOST", renderer)
        self.assertIn("PSYCHIC EQUILIBRIUM", renderer)
        self.assertIn("resultOutcome", renderer)
        self.assertIn("state.game.result?.is_draw", renderer)
        self.assertIn("state.game.result?.is_winner", renderer)
        self.assertIn("shouldShowResultOverlay", renderer)
        self.assertIn("resultReasonText", renderer)
        self.assertIn("renderResultCardFan", renderer)
        self.assertIn("state.opponent.hand || []", renderer)
        self.assertIn("outcome-", renderer)
        self.assertIn('"--victory-color"', renderer)
        self.assertIn('"--result-secondary-color"', renderer)
        self.assertIn("Math.min(Math.max(dominant.count, 1), 3)", renderer)
        self.assertIn("renderVictoryOverlay(state, handlers)", renderer)

        self.assertIn(".outcome-defeat", css)
        self.assertIn(".outcome-draw", css)
        self.assertIn(".victory-card-display", css)
        self.assertIn("@keyframes victory-title-enter", css)
        self.assertIn("@keyframes defeat-sigil-flicker", css)
        self.assertIn("@keyframes draw-sigil-balance", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

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
        html = (FRONTEND_ROOT / "index.html").read_text()
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
        self.assertIn('id="turn-start-guide"', html)
        self.assertIn("カードを1枚捨てる", html)
        self.assertIn("山札から1枚引く", html)
        self.assertIn("手札からカードを1枚選んで捨て", renderer)
        self.assertIn("showTurnGuide", renderer)
        self.assertIn("isMyTurn ? 3400 : 2000", renderer)
        self.assertIn(".action-event-overlay.tone-turn-mine", css)
        self.assertIn(".action-event-overlay.tone-turn-opponent", css)
        self.assertIn(".turn-start-guide", css)

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

    def test_hero_title_has_balanced_responsive_sizes(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        self.assertIn(".hero-panel > .eyebrow", css)
        self.assertIn("font-size: clamp(17px, 1.6vw, 22px)", css)
        self.assertIn("font-size: clamp(64px, 9.5vw, 132px)", css)
        self.assertIn("font-size: clamp(58px, 17vw, 82px)", css)

    def test_log_and_chat_are_hidden_behind_utility_buttons(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        for panel in ("log", "chat"):
            self.assertIn(f'id="{panel}-toggle-button"', html)
            self.assertIn(f'aria-controls="{panel}-panel"', html)
            self.assertIn(f'id="{panel}-panel"', html)
            self.assertIn(f'id="{panel}-close-button"', html)
        self.assertIn('id="utility-panel-backdrop"', html)
        self.assertNotIn('class="side-column"', html)
        self.assertIn("setUtilityPanel", app)
        self.assertIn('openPanel === "log"', app)
        self.assertIn('openPanel === "chat"', app)
        self.assertIn("utilityPanelBackdrop.hidden", app)
        self.assertIn(".utility-toggle-button", css)
        self.assertIn(".utility-panel", css)
        self.assertIn(".utility-panel-backdrop", css)

    def test_cards_use_ability_specific_tarot_skin(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn("CARD_ART_FILES", renderer)
        self.assertIn("decorateVisibleCard", renderer)
        self.assertIn("node.dataset.cardName = name", renderer)
        self.assertIn("if (name && !hidden)", renderer)
        self.assertIn("Illustrated ivory ability cards", css)
        for card in (
            "クレヤボヤンス",
            "タイムリープ",
            "サイコキネシス",
            "プリサイエンス",
            "テレポート",
            "ヒーリング",
            "カモフラージュ",
        ):
            self.assertIn(f'.card[data-card-name="{card}"]', css)
        self.assertIn(".card::before", css)
        self.assertIn(".card::after", css)
        self.assertIn(".card.hidden-card", css)
        self.assertIn(".card.selected:not(.hidden-card)", css)
        self.assertIn("color-mix(in srgb, var(--card-accent)", css)
        expected_colors = {
            "クレヤボヤンス": "#f59a2a",
            "タイムリープ": "#20b8d4",
            "サイコキネシス": "#e55b9a",
            "プリサイエンス": "#18aaa9",
            "テレポート": "#247fbd",
            "ヒーリング": "#ef6264",
            "カモフラージュ": "#8171bd",
        }
        for card, color in expected_colors.items():
            selector = f'.card[data-card-name="{card}"] {{'
            block = css.split(selector, 1)[1].split("}", 1)[0]
            self.assertIn(f"--card-accent: {color}", block)

    def test_landscape_hand_uses_discard_popover(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        for owner in ("my", "opponent"):
            self.assertIn(f'id="{owner}-discard-toggle-button"', html)
            self.assertIn(f'aria-controls="{owner}-discard-panel"', html)
            self.assertIn(f'id="{owner}-discard-panel"', html)
            self.assertIn(f'id="{owner}-discard-count"', html)
            self.assertIn(f'id="{owner}-discards" class="discard-row"', html)
        self.assertEqual(html.count("battle-hand-row"), 2)
        self.assertIn("setDiscardPanelOpen", app)
        self.assertIn("syncDiscardLayout", app)
        self.assertIn('matchMedia("(orientation: landscape)")', app)
        self.assertIn("myDiscardCount", renderer)
        self.assertIn("opponentDiscardCount", renderer)
        self.assertIn('state.interaction?.kind === "healing"', renderer)
        self.assertIn(".battle-hand-row", css)
        self.assertIn("repeat(6, minmax(0, 92px))", css)
        self.assertIn("overflow: visible", css)
        self.assertIn(".discard-toggle-button", css)
        self.assertIn(".discard-popover", css)
        self.assertIn("repeat(6, minmax(0, 61px))", css)
        self.assertIn(".discard-popover-header", css)

    def test_discard_overlay_stays_visible_above_context_actions(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn("discard-panel-open", app)
        self.assertIn("discardPanelAnchors", app)
        self.assertIn("placeDiscardPanel", app)
        self.assertIn("document.body.append(panel)", app)
        self.assertIn("parent.insertBefore(panel, nextSibling)", app)
        self.assertIn("body.game-active.discard-panel-open .table-panel", css)
        self.assertIn("body.game-active.discard-panel-open::before", css)
        self.assertIn("body.game-active > .discard-popover", css)
        self.assertIn("top: 50%", css)
        self.assertIn("left: 50%", css)
        self.assertIn("transform: translate(-50%, -50%)", css)
        self.assertIn("z-index: 40", css)
        self.assertIn("position: fixed", css)
        self.assertIn("overflow-y: auto", css)

    def test_opponent_discard_overlay_uses_opponent_red_accent(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        selector = "body.game-active > #opponent-discard-panel"
        self.assertIn(selector, css)
        block = css.split(f"{selector} {{", 1)[1].split("}", 1)[0]
        self.assertIn("rgba(255, 100, 117, 0.62)", block)
        self.assertIn("rgba(18, 10, 20, 0.98)", block)
        self.assertIn(
            f"{selector} .discard-popover-header",
            css,
        )
        self.assertIn(
            f"{selector} .discard-popover-close",
            css,
        )

    def test_desktop_discard_overlay_uses_larger_cards(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        self.assertIn(
            "@media (min-width: 1024px) and (orientation: landscape)",
            css,
        )
        self.assertIn("width: min(760px, calc(100vw - 48px))", css)
        self.assertIn("repeat(6, minmax(0, 96px))", css)
        self.assertIn("width: 90px", css)
        self.assertIn("height: 124px", css)

    def test_discard_selection_confirmation_closes_landscape_overlay(self):
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn("DISCARD_SELECTION_CONFIRM_ACTIONS", app)
        self.assertIn('"confirm_healing"', app)
        self.assertIn('"confirm_clairvoyance"', app)
        self.assertIn('"select_psychokinesis_push"', app)
        self.assertIn("DISCARD_SELECTION_CONFIRM_ACTIONS.has(action)", app)
        self.assertIn("closeDiscardPanels()", app)

    def test_visible_cards_show_details_on_hover_or_long_press(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn('id="card-detail-tooltip"', html)
        self.assertIn('id="card-detail-name"', html)
        self.assertIn('id="card-detail-effect"', html)
        self.assertIn("initializeCardDetails", renderer)
        self.assertIn("CARD_DETAIL_LONG_PRESS_MS", renderer)
        self.assertIn('matchMedia("(hover: hover) and (pointer: fine)")', renderer)
        self.assertIn('event.pointerType === "mouse"', renderer)
        self.assertIn("CARD_EFFECTS[name]", renderer)
        self.assertIn(".card-detail-tooltip", css)
        self.assertIn("@keyframes card-detail-appear", css)

    def test_illustrated_cards_do_not_use_corner_squares(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        illustrated = css.split("/* Illustrated ivory ability cards */", 1)[1]
        illustrated = illustrated.split("/* Strong draw-ready deck glow */", 1)[0]

        self.assertNotIn("top 7px left 7px / 6px 6px", illustrated)
        self.assertNotIn("bottom 7px right 7px / 6px 6px", illustrated)

    def test_session_information_is_hidden_in_slide_panel(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertNotIn('<header class="room-bar">', html)
        self.assertIn('id="session-toggle-button"', html)
        self.assertIn('aria-controls="session-panel"', html)
        self.assertIn('class="hamburger-icon"', html)
        self.assertIn('id="session-panel"', html)
        self.assertIn('id="room-player"', html)
        self.assertIn('id="connection-status"', html)
        self.assertIn('id="copy-room-button"', html)
        self.assertIn('id="leave-button"', html)
        self.assertIn('openPanel === "session"', app)
        self.assertIn("sessionPanel.hidden", app)
        self.assertIn("sessionToggleButton.classList.toggle", app)
        self.assertIn(".session-toggle-button", css)
        self.assertIn(".hamburger-icon", css)
        self.assertIn(".session-panel", css)
        self.assertIn(".session-panel-content", css)

    def test_landscape_game_fits_inside_viewport_without_page_scroll(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        app = (
            FRONTEND_ROOT / "static" / "js" / "app.js"
        ).read_text()

        self.assertIn('document.body.classList.add("game-active")', app)
        self.assertIn('document.body.classList.remove("game-active")', app)
        self.assertIn("Fit the landscape battle board within the viewport", css)
        self.assertIn("body.game-active", css)
        self.assertIn("height: 100dvh", css)
        self.assertIn("overflow: hidden", css)
        self.assertIn("body.game-active .site-header", css)
        self.assertIn("grid-template-rows:", css)
        self.assertIn("clamp(92px, 24dvh, 210px)", css)
        self.assertIn("height: clamp(60px, 18dvh, 138px)", css)
        self.assertIn("height: clamp(46px, 13dvh, 92px)", css)
        self.assertIn(
            "height: clamp(58px, min(18dvh, 11vw), 164px)",
            css,
        )

    def test_landscape_cards_hide_names_and_scale_with_viewport(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        self.assertIn("Responsive landscape card scale", css)
        self.assertIn("body.game-active .game-screen .card-name", css)
        self.assertIn("display: none", css)
        self.assertIn("repeat(6, minmax(0, 126px))", css)
        self.assertIn(
            "height: clamp(58px, min(18dvh, 11vw), 164px)",
            css,
        )
        self.assertIn("@media (min-width: 1440px)", css)
        self.assertIn(
            "height: clamp(142px, min(19dvh, 10vw), 178px)",
            css,
        )

    def test_landscape_context_actions_do_not_resize_board(self):
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()
        renderer = (
            FRONTEND_ROOT / "static" / "js" / "render.js"
        ).read_text()

        self.assertIn('classList.toggle("has-context-actions", visible)', renderer)
        self.assertIn("Stable floating actions in landscape", css)
        self.assertIn(
            "body.game-active .game-screen.has-context-actions",
            css,
        )
        self.assertIn("padding-bottom: 0", css)
        self.assertIn("width: min(760px, calc(100% - 16px))", css)
        self.assertIn(".my-zone > .discard-access", css)
        self.assertIn("translate: 0 clamp(-18px, -2.5dvh, -8px)", css)

    def test_card_svg_art_is_served_for_all_abilities(self):
        expected_files = (
            "clairvoyance.svg",
            "time-leap.svg",
            "psychokinesis.svg",
            "prescience.svg",
            "teleport.svg",
            "healing.svg",
            "camouflage.svg",
        )
        for file_name in expected_files:
            response = self.client.get(f"/static/assets/cards/{file_name}")
            self.assertEqual(response.status_code, 200)
            self.assertIn("image/svg+xml", response.headers["content-type"])
            self.assertIn("<svg", response.text)

    def test_battle_board_uses_landscape_first_layout(self):
        html = (FRONTEND_ROOT / "index.html").read_text()
        css = (
            FRONTEND_ROOT / "static" / "css" / "styles.css"
        ).read_text()

        self.assertIn('class="arena-mark"', html)
        self.assertIn('class="excluded-zone"', html)
        self.assertIn("Landscape-first battle board", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr)", css)
        self.assertIn("@media (max-width: 760px) and (orientation: landscape)", css)

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
