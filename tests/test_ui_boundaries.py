import ast
import unittest
from pathlib import Path


class UiBoundaryTests(unittest.TestCase):
    def test_ui_does_not_directly_mutate_game_state(self):
        ui_path = Path(__file__).parents[1] / "ui_views.py"
        tree = ast.parse(
            ui_path.read_text(encoding="utf-8"),
            filename=str(ui_path),
        )
        violations = []
        mutating_game_methods = {
            "add_log",
            "end_action",
            "fill_hand_to_6",
            "reset_game",
            "trigger_draw",
            "trigger_endgame",
        }
        collection_mutators = {
            "add",
            "append",
            "clear",
            "extend",
            "pop",
            "remove",
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = (
                    node.targets
                    if isinstance(node, ast.Assign)
                    else [node.target]
                )
                for target in targets:
                    if (
                        isinstance(target, ast.Attribute)
                        and isinstance(target.value, ast.Name)
                        and target.value.id == "game"
                    ):
                        violations.append(
                            f"line {node.lineno}: assignment to game.{target.attr}"
                        )

            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and isinstance(function.value, ast.Name)
                and function.value.id == "game"
                and function.attr in mutating_game_methods
            ):
                violations.append(
                    f"line {node.lineno}: call to game.{function.attr}"
                )
            if (
                isinstance(function, ast.Attribute)
                and function.attr in collection_mutators
                and isinstance(function.value, ast.Attribute)
                and isinstance(function.value.value, ast.Name)
                and function.value.value.id == "game"
            ):
                violations.append(
                    f"line {node.lineno}: mutation of game.{function.value.attr}"
                )

        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
