"""Checker for sequential async_add_entities calls.

Multiple sequential ``async_add_entities()`` calls should be grouped into a
single call, so all entities are added to the platform in one go. Calls are
sequential when only statements that can't suspend or leave the function run
between them, also when the later call is nested in an ``if`` or ``with``.

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

# Grouping calls across these changes when (or whether) entities are added
BARRIER_NODES = (
    nodes.Await,
    nodes.Yield,
    nodes.YieldFrom,
    nodes.Return,
    nodes.Raise,
    nodes.Break,
    nodes.Continue,
)
SCOPE_NODES = (nodes.FunctionDef, nodes.Lambda, nodes.ClassDef)


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


def _contains_add_entities_call(node: nodes.NodeNG) -> bool:
    """Return whether *node* contains an ``async_add_entities(...)`` statement."""
    return any(
        _get_add_entities_call(expr) is not None
        for expr in node.nodes_of_class(nodes.Expr, skip_klass=SCOPE_NODES)
    )


def _is_barrier(node: nodes.NodeNG) -> bool:
    """Return whether *node* can suspend or leave the function."""
    return (
        next(node.nodes_of_class(BARRIER_NODES, skip_klass=SCOPE_NODES), None)
        is not None
    )


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

    def _check_body(
        self, body: list[nodes.NodeNG], prev_arguments: list[str] | None = None
    ) -> None:
        """Check a list of statements for sequential async_add_entities calls.

        *prev_arguments* are the arguments of a call that precedes the block.
        """
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

            # Defining a nested function runs none of its body
            if isinstance(stmt, SCOPE_NODES):
                continue

            if not _contains_add_entities_call(stmt):
                if _is_barrier(stmt):
                    prev_arguments = None
                continue

            # A preceding call carries into branches, but not into loops, which
            # can run the nested call more than once
            if isinstance(stmt, nodes.If):
                carried = None if _is_barrier(stmt.test) else prev_arguments
                self._check_body(stmt.body, carried)
                self._check_body(stmt.orelse, carried)
            elif isinstance(stmt, nodes.Try):
                self._check_body(stmt.body, prev_arguments)
                for handler in stmt.handlers:
                    self._check_body(handler.body)
                self._check_body(stmt.orelse)
                self._check_body(stmt.finalbody)
            elif isinstance(stmt, nodes.AsyncWith):
                self._check_body(stmt.body)
            elif isinstance(stmt, nodes.With):
                carried = (
                    None
                    if any(_is_barrier(item) for item, _ in stmt.items)
                    else prev_arguments
                )
                self._check_body(stmt.body, carried)
            elif isinstance(stmt, (nodes.For, nodes.AsyncFor, nodes.While)):
                self._check_body(stmt.body)
                self._check_body(stmt.orelse)

            # Which nested calls ran is only known at runtime
            prev_arguments = None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(SequentialAddEntitiesChecker(linter))
