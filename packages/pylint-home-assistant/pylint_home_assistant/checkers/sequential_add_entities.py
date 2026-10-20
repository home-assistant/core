"""Checker for sequential async_add_entities calls.

Multiple sequential ``async_add_entities()`` calls should be grouped into a
single call, so all entities are added to the platform in one go.

Calls with different keyword arguments (for example a different
``config_subentry_id``) cannot be grouped and are not flagged.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

ADD_ENTITIES_CALLBACK_NAMES = {"async_add_entities", "add_entities"}


def _get_add_entities_call(node: nodes.NodeNG) -> nodes.Call | None:
    """Return the call if *node* is an ``async_add_entities(...)`` statement."""
    if not isinstance(node, nodes.Expr) or not isinstance(node.value, nodes.Call):
        return None

    call = node.value
    if (
        not isinstance(call.func, nodes.Name)
        or call.func.name not in ADD_ENTITIES_CALLBACK_NAMES
    ):
        return None

    # Only the callback passed to the platform setup function, not a local helper
    _, assignments = call.func.lookup(call.func.name)
    if not assignments or not all(
        isinstance(assignment.parent, nodes.Arguments) for assignment in assignments
    ):
        return None

    return call


def _keywords(call: nodes.Call) -> list[str] | None:
    """Return the keyword arguments of *call*, or None if they are unknown."""
    if any(keyword.arg is None for keyword in call.keywords):
        return None
    return sorted(keyword.as_string() for keyword in call.keywords)


class SequentialAddEntitiesChecker(BaseChecker):
    """Checker for sequential async_add_entities calls."""

    name = "home_assistant_sequential_add_entities"
    priority = -1
    msgs = {
        "W7454": (
            "Sequential `%s` calls should be grouped into a single call",
            "home-assistant-sequential-add-entities",
            "Used when multiple async_add_entities() calls with the same "
            "keyword arguments appear in sequence. Collect the entities and "
            "call async_add_entities once.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check for sequential async_add_entities calls."""
        if not self._in_integration:
            return

        self._check_body(node.body)

    visit_asyncfunctiondef = visit_functiondef

    def _check_body(self, body: list[nodes.NodeNG]) -> None:
        """Check a list of statements for sequential async_add_entities calls."""
        prev_keywords: list[str] | None = None

        for stmt in body:
            if (call := _get_add_entities_call(stmt)) is not None:
                keywords = _keywords(call)
                if keywords is not None and keywords == prev_keywords:
                    self.add_message(
                        "home-assistant-sequential-add-entities",
                        node=stmt,
                        args=(call.func.name,),
                    )
                prev_keywords = keywords
                continue

            prev_keywords = None

            # Recurse into control flow blocks (but not nested functions)
            if isinstance(stmt, nodes.If):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)
            elif isinstance(stmt, nodes.Try):
                self._check_body(stmt.body)
                for handler in stmt.handlers:
                    self._check_body(handler.body)
                self._check_body(stmt.orelse)
                self._check_body(stmt.finalbody)
            elif isinstance(stmt, (nodes.With, nodes.AsyncWith)):
                self._check_body(stmt.body)
            elif isinstance(stmt, (nodes.For, nodes.AsyncFor, nodes.While)):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialAddEntitiesChecker(linter))
