"""Checker for the position of the ``if TYPE_CHECKING:`` block.

``C7464`` (``home-assistant-type-checking-block-position``)
-----------------------------------------------------------
Fires when a module-level ``if TYPE_CHECKING:`` block is followed by a
module-level import. Neither ruff nor pylint flag this, because both allow
conditional blocks between imports.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter


def _is_type_checking_block(node: nodes.NodeNG) -> bool:
    """Return whether the node is an ``if TYPE_CHECKING:`` block."""
    if not isinstance(node, nodes.If):
        return False
    test = node.test
    return (isinstance(test, nodes.Name) and test.name == "TYPE_CHECKING") or (
        isinstance(test, nodes.Attribute)
        and test.attrname == "TYPE_CHECKING"
        and isinstance(test.expr, nodes.Name)
        and test.expr.name == "typing"
    )


class HassTypeCheckingBlockChecker(BaseChecker):
    """Checker that ``if TYPE_CHECKING:`` comes after all imports."""

    name = "home_assistant_type_checking_block"
    priority = -1
    msgs = {
        "C7464": (
            "`if TYPE_CHECKING:` block should be placed after all module-level imports",
            "home-assistant-type-checking-block-position",
            (
                "Used when a module-level import follows an `if TYPE_CHECKING:` "
                "block. Move the block below the last import."
            ),
        ),
    }
    options = ()

    def visit_module(self, node: nodes.Module) -> None:
        """Flag a ``TYPE_CHECKING`` block followed by an import."""
        type_checking_block: nodes.If | None = None
        for item in node.body:
            if type_checking_block is None:
                if _is_type_checking_block(item):
                    type_checking_block = item
            elif isinstance(item, (nodes.Import, nodes.ImportFrom)):
                self.add_message(
                    "home-assistant-type-checking-block-position",
                    node=type_checking_block,
                )
                return


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassTypeCheckingBlockChecker(linter))
