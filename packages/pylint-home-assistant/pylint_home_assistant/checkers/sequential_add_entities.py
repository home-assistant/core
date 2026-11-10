"""Checker for sequential async_add_entities calls.

Multiple sequential ``async_add_entities()`` calls should be grouped into a
single call, so all entities are added to the platform in one go.

Calls with different arguments besides the entities (for example a different
``config_subentry_id`` or ``update_before_add``) cannot be grouped and are not
flagged.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

ADD_ENTITIES_CALLBACK_NAMES = {"async_add_entities", "add_entities"}
PLATFORM_SETUP_FUNCTIONS = {
    "async_setup_entry",
    "async_setup_platform",
    "setup_platform",
}


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
    # or a parameter of a nested function shadowing it
    _, assignments = call.func.lookup(call.func.name)
    if not assignments or not all(
        isinstance(assignment.parent, nodes.Arguments)
        and isinstance(setup := assignment.parent.parent, nodes.FunctionDef)
        and setup.name in PLATFORM_SETUP_FUNCTIONS
        and isinstance(setup.parent, nodes.Module)
        for assignment in assignments
    ):
        return None

    return call


def _extra_arguments(call: nodes.Call) -> list[str] | None:
    """Return the arguments of *call* besides the entities, or None if unknown."""
    if any(isinstance(arg, nodes.Starred) for arg in call.args) or any(
        keyword.arg is None for keyword in call.keywords
    ):
        return None
    keywords = [keyword for keyword in call.keywords if keyword.arg != "new_entities"]
    # Calls can return a different value each time, despite identical source
    if any(
        next(node.nodes_of_class(nodes.Call), None) is not None
        for node in (*call.args[1:2], *keywords)
    ):
        return None
    # update_before_add can also be passed positionally
    arguments = [f"update_before_add={arg.as_string()}" for arg in call.args[1:2]]
    arguments.extend(keyword.as_string() for keyword in keywords)
    return sorted(arguments)


class SequentialAddEntitiesChecker(BaseChecker):
    """Checker for sequential async_add_entities calls."""

    name = "home_assistant_sequential_add_entities"
    priority = -1
    msgs = {
        "W7454": (
            "Sequential `%s` calls should be grouped into a single call",
            "home-assistant-sequential-add-entities",
            "Used when multiple async_add_entities() calls with the same "
            "arguments besides the entities appear in sequence. Collect the entities and "
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
        prev_arguments: list[str] | None = None

        for stmt in body:
            if (call := _get_add_entities_call(stmt)) is not None:
                arguments = _extra_arguments(call)
                if arguments is not None and arguments == prev_arguments:
                    self.add_message(
                        "home-assistant-sequential-add-entities",
                        node=stmt,
                        args=(call.func.name,),
                    )
                prev_arguments = arguments
                continue

            prev_arguments = None

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
