"""Checker for manual coordinator refreshes in integration tests.

Tests should not refresh a ``DataUpdateCoordinator`` by calling
``async_refresh``, ``async_request_refresh`` or ``_async_refresh``. Instead,
tests should advance the time with ``freezer.tick(...)``, fire
``async_fire_time_changed(hass)`` and wait with
``await hass.async_block_till_done(wait_background_tasks=True)``, so that the
coordinator's own scheduling is exercised.

Coordinators usually reach a test through ``entry.runtime_data`` or a
fixture, which astroid cannot infer. Every use of one of these methods in a
``tests.components`` module is therefore flagged, unless the receiver is
inferred to be an instance of a class that is not a ``DataUpdateCoordinator``
(for example a mock or a local helper class). Passing the bound method around
without calling it (for example to ``hass.async_add_job``) is flagged too.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module, parse_module

_COORDINATOR_QNAME = "homeassistant.helpers.update_coordinator.DataUpdateCoordinator"
_PUBLIC_REFRESH_METHODS = frozenset({"async_refresh", "async_request_refresh"})
_REFRESH_METHODS = _PUBLIC_REFRESH_METHODS | {"_async_refresh"}


def _is_other_receiver(receiver: nodes.NodeNG) -> bool:
    """Return True if *receiver* is known not to be a coordinator."""
    try:
        inferred = list(receiver.infer())
    except astroid.exceptions.AstroidError:
        return False

    # A single uninferable value could still be the coordinator
    if any(value is astroid.Uninferable for value in inferred):
        return False

    # A getter typed ``... | None`` also infers to None
    inferred = [
        value
        for value in inferred
        if not (isinstance(value, nodes.Const) and value.value is None)
    ]
    if not inferred:
        return False

    return all(
        isinstance(value, astroid.Instance)
        and not value.is_subtype_of(_COORDINATOR_QNAME)
        for value in inferred
    )


class CoordinatorAsyncRefresh(BaseChecker):
    """Checker for manual coordinator refreshes in integration tests."""

    name = "home_assistant_tests_coordinator_async_refresh"
    priority = -1
    msgs = {
        "W7439": (
            (
                "Do not trigger a refresh directly in tests; advance the time "
                "with `freezer.tick()` and `async_fire_time_changed()` instead"
            ),
            "home-assistant-tests-coordinator-async-refresh",
            (
                "Used when an integration test calls `async_refresh()`, "
                "`async_request_refresh()` or `_async_refresh()`, or passes one "
                "of them around. Tests should advance the time so the "
                "coordinator refreshes on its own schedule."
            ),
        ),
    }
    options = ()

    _in_component_test: bool = False

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the current module is an integration test module."""
        self._in_component_test = (
            is_test_module(node.name)
            and parse_module(node.name, include_test=True) is not None
        )

    def visit_attribute(self, node: nodes.Attribute) -> None:
        """Flag uses of a coordinator refresh method."""
        if not self._in_component_test or node.attrname not in _REFRESH_METHODS:
            return

        # Accessing attributes of the method itself, such as
        # ``mock.async_refresh.assert_called()``, does not refresh anything
        if isinstance(node.parent, nodes.Attribute):
            return

        # The public refresh methods take no arguments, so a call with
        # arguments is an unrelated method, such as ``info.async_refresh(now)``
        if (
            node.attrname in _PUBLIC_REFRESH_METHODS
            and isinstance(node.parent, nodes.Call)
            and node.parent.func is node
            and (node.parent.args or node.parent.keywords)
        ):
            return

        if _is_other_receiver(node.expr):
            return

        self.add_message("home-assistant-tests-coordinator-async-refresh", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(CoordinatorAsyncRefresh(linter))
