"""Checker for ``async_refresh()`` calls in integration tests.

Tests should not refresh a ``DataUpdateCoordinator`` by calling its
``async_refresh`` method. Instead, tests should advance the time with
``freezer.tick(...)``, fire ``async_fire_time_changed(hass)`` and wait with
``await hass.async_block_till_done(wait_background_tasks=True)``, so that the
coordinator's own scheduling is exercised.

Coordinators usually reach a test through ``entry.runtime_data`` or a
fixture, which astroid cannot infer. Every ``<expr>.async_refresh()`` call
without arguments in a ``tests.components`` module is therefore flagged,
unless the receiver is inferred to be an instance of a class that is not a
``DataUpdateCoordinator`` (for example a mock or a local helper class).
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_COORDINATOR_QNAME = "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"


def _is_other_receiver(receiver: nodes.NodeNG) -> bool:
    """Return True if *receiver* is known not to be a coordinator."""
    try:
        # A getter typed ``... | None`` also infers to None
        inferred = [
            value
            for value in receiver.infer()
            if value is not astroid.Uninferable
            and not (isinstance(value, nodes.Const) and value.value is None)
        ]
    except astroid.exceptions.InferenceError, astroid.exceptions.AstroidError:
        return False
    if not inferred:
        return False
    return all(
        isinstance(value, astroid.Instance)
        and not value.is_subtype_of(_COORDINATOR_QNAME)
        for value in inferred
    )


class CoordinatorAsyncRefresh(BaseChecker):
    """Checker for async_refresh calls in integration tests."""

    name = "home_assistant_tests_coordinator_async_refresh"
    priority = -1
    msgs = {
        "W7439": (
            (
                "Do not call `async_refresh()` on a coordinator in tests; "
                "advance the time with `freezer.tick()` and "
                "`async_fire_time_changed()` instead"
            ),
            "home-assistant-tests-coordinator-async-refresh",
            (
                "Used when an integration test calls `async_refresh()`. Tests "
                "should advance the time so the coordinator refreshes on its "
                "own schedule."
            ),
        ),
    }
    options = ()

    _in_component_test: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is an integration test module."""
        self._in_component_test = node.name.startswith("tests.components.")

    def visit_call(self, node: nodes.Call) -> None:
        """Flag ``<expr>.async_refresh()`` calls."""
        if not self._in_component_test:
            return
        match node.func:
            case nodes.Attribute(attrname="async_refresh", expr=receiver) if (
                not node.args and not node.keywords
            ):
                pass
            case _:
                return
        if _is_other_receiver(receiver):
            return
        self.add_message("home-assistant-tests-coordinator-async-refresh", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorAsyncRefresh(linter))
