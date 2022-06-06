"""Plugin for constructor definitions."""
from __future__ import annotations

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


class HassConstructorFormatChecker(BaseChecker):  # type: ignore[misc]
    """Checker for __init__ definitions."""

    name = "hass_constructor"
    priority = -1
    msgs = {
        "W7411": (
            '__init__ should have explicit return type "None"',
            "hass-constructor-return",
            "Used when __init__ has all arguments typed "
            "but doesn't have return type declared",
        ),
    }
    options = ()

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Called when a FunctionDef node is visited."""
        if not node.is_method() or node.name != "__init__":
            return

        # Check that all arguments are annotated.
        # The first argument is "self".
        args = node.args
        annotations = (
            args.posonlyargs_annotations
            + args.annotations
            + args.kwonlyargs_annotations
        )[1:]
        if args.vararg is not None:
            annotations.append(args.varargannotation)
        if args.kwarg is not None:
            annotations.append(args.kwargannotation)
        if not annotations or None in annotations:
            return

        # Check that return type is specified and it is "None".
        if not isinstance(node.returns, nodes.Const) or node.returns.value is not None:
            self.add_message("hass-constructor-return", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassConstructorFormatChecker(linter))
