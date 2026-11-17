"""Checker for redundant ``caplog`` DEBUG levels in tests.

The ``caplog`` fixture of ``pytest_homeassistant`` already calls
``caplog.set_level(logging.DEBUG)`` before the test runs, so every test that
uses ``caplog`` captures all log records at DEBUG and above. Calling::

    caplog.set_level(logging.DEBUG)

or::

    with caplog.at_level(logging.DEBUG):
        ...

without a ``logger`` argument therefore changes nothing.

Calls that pass a ``logger`` are not checked: some code sets the level of
its own loggers, so lowering a named logger to DEBUG can be needed. Calls
that follow ``caplog.set_level`` with another level in the same function,
or that are inside a ``with caplog.at_level(...)`` block with another
level, are not checked either, as they restore the DEBUG level.
"""

import logging

from astroid import nodes
from pylint.checkers import BaseChecker, utils
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_CAPLOG = "caplog"
_LEVEL_METHODS = frozenset({"set_level", "at_level"})
_DEBUG_LEVELS = frozenset({logging.DEBUG, "DEBUG"})


def _caplog_level_call(node: nodes.Call) -> tuple[str, nodes.NodeNG] | None:
    """Return the method and level of a root ``caplog`` level call.

    Returns ``None`` when *node* is not a ``caplog.set_level`` or
    ``caplog.at_level`` call, or when it targets a named logger.
    """
    func = node.func
    if not (
        isinstance(func, nodes.Attribute)
        and func.attrname in _LEVEL_METHODS
        and isinstance(func.expr, nodes.Name)
        and func.expr.name == _CAPLOG
    ):
        return None

    level: nodes.NodeNG | None = node.args[0] if node.args else None
    logger: nodes.NodeNG | None = node.args[1] if len(node.args) > 1 else None
    for keyword in node.keywords or ():
        if keyword.arg == "level":
            level = keyword.value
        elif keyword.arg == "logger":
            logger = keyword.value

    if level is None:
        return None
    if logger is not None and not (
        isinstance(logger, nodes.Const) and logger.value is None
    ):
        return None
    return func.attrname, level


def _is_debug_level(level: nodes.NodeNG) -> bool:
    """Return True when *level* resolves to the DEBUG level."""
    inferred = utils.safe_infer(level)
    return isinstance(inferred, nodes.Const) and inferred.value in _DEBUG_LEVELS


class RedundantCaplogLevelChecker(BaseChecker):
    """Checker for ``caplog`` calls that set the level already in use."""

    name = "home_assistant_tests_redundant_caplog_level"
    priority = -1
    msgs = {
        "R7406": (
            "`caplog.%s(logging.DEBUG)` is redundant, the caplog fixture "
            "already captures DEBUG logs",
            "home-assistant-tests-redundant-caplog-level",
            "Used when a test sets the root caplog level to DEBUG. The "
            "caplog fixture of pytest_homeassistant already sets it to DEBUG.",
        ),
    }
    options = ()

    _active: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Record whether the module is a test module."""
        self._active = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Flag ``caplog`` calls that set the root level to DEBUG."""
        if not self._active:
            return

        if (call := _caplog_level_call(node)) is None:
            return
        method, level = call
        if not _is_debug_level(level):
            return

        if self._follows_other_level(node):
            return

        self.add_message(
            "home-assistant-tests-redundant-caplog-level",
            node=node,
            args=(method,),
        )

    @staticmethod
    def _follows_other_level(node: nodes.Call) -> bool:
        """Return True when the call restores DEBUG after a higher level.

        That is the case after an earlier ``caplog.set_level`` with another
        level, or inside a ``with caplog.at_level(...)`` block with another
        level, as the DEBUG call then lowers the level again.
        """
        ancestors = set(node.node_ancestors())
        for other in node.frame().nodes_of_class(nodes.Call):
            if other is node or other.lineno >= node.lineno:
                continue
            if (call := _caplog_level_call(other)) is None:
                continue
            method, level = call
            if _is_debug_level(level):
                continue
            if method == "set_level" or other.parent in ancestors:
                return True
        return False


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantCaplogLevelChecker(linter))
