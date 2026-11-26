"""Checker for redundant ``caplog`` DEBUG levels in tests.

The ``caplog`` fixture of ``pytest_homeassistant`` already calls
``caplog.set_level(logging.DEBUG)`` before the test runs, so every test that
uses ``caplog`` captures all log records at DEBUG and above. Calling::

    caplog.set_level(logging.DEBUG)

or::

    with caplog.at_level(logging.DEBUG):
        ...

without a ``logger`` argument therefore changes nothing.

Calls that pass a ``logger``, or unpack their arguments, are not checked:
some code sets the level of its own loggers, so lowering a named logger to
DEBUG can be needed.

Both methods also set the level of the shared capture handler, even with a
``logger``. A DEBUG call is therefore not checked either when the level may
be different at that point, which is the case when it:

* follows ``caplog.set_level`` with another level in the same function,
* is inside a ``with caplog.at_level(...)`` block with another level,
* is in a function nested in one that sets another level, or
* is a ``with caplog.at_level(logging.DEBUG)`` block whose body calls
  ``caplog.set_level`` with another level, which the block undoes on exit.
"""

from dataclasses import dataclass
import logging

from astroid import nodes
from pylint.checkers import BaseChecker, utils
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_test_module

_CAPLOG = "caplog"
_LEVEL_METHODS = frozenset({"set_level", "at_level"})
_DEBUG_LEVELS = frozenset({logging.DEBUG, "DEBUG"})


@dataclass(frozen=True, slots=True)
class _LevelCall:
    """A ``caplog.set_level`` or ``caplog.at_level`` call."""

    method: str
    level: nodes.NodeNG | None
    root_logger: bool
    unpacked: bool

    @property
    def sets_debug(self) -> bool:
        """Return True when the call is known to set the DEBUG level."""
        return not self.unpacked and _is_debug_level(self.level)


def _parse_level_call(node: nodes.Call) -> _LevelCall | None:
    """Return the parsed call, or ``None`` if it is not a caplog level call."""
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
    unpacked = any(isinstance(arg, nodes.Starred) for arg in node.args)
    for keyword in node.keywords or ():
        if keyword.arg is None:
            unpacked = True
        elif keyword.arg == "level":
            level = keyword.value
        elif keyword.arg == "logger":
            logger = keyword.value

    return _LevelCall(
        method=func.attrname,
        level=level,
        root_logger=logger is None
        or (isinstance(logger, nodes.Const) and logger.value is None),
        unpacked=unpacked,
    )


def _is_debug_level(level: nodes.NodeNG | None) -> bool:
    """Return True when *level* resolves to the DEBUG level."""
    if level is None:
        return False
    inferred = utils.safe_infer(level)
    return isinstance(inferred, nodes.Const) and inferred.value in _DEBUG_LEVELS


def _level_calls(node: nodes.NodeNG) -> list[tuple[nodes.Call, _LevelCall]]:
    """Return the caplog level calls in *node*, including *node* itself."""
    return [
        (call, parsed)
        for call in node.nodes_of_class(nodes.Call)
        if (parsed := _parse_level_call(call)) is not None
    ]


class RedundantCaplogLevelChecker(BaseChecker):
    """Checker for ``caplog`` calls that set the level already in use."""

    name = "home_assistant_tests_redundant_caplog_level"
    priority = -1
    msgs = {
        "R7407": (
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

        call = _parse_level_call(node)
        if call is None or not call.root_logger or not call.sets_debug:
            return

        if (
            self._follows_other_level(node)
            or self._nested_in_other_level(node)
            or self._block_sets_other_level(node, call)
        ):
            return

        self.add_message(
            "home-assistant-tests-redundant-caplog-level",
            node=node,
            args=(call.method,),
        )

    @staticmethod
    def _follows_other_level(node: nodes.Call) -> bool:
        """Return True when an earlier call in the function sets another level.

        That is an earlier ``caplog.set_level``, or an enclosing
        ``with caplog.at_level(...)``, for any logger, as both also set the
        level of the shared capture handler.
        """
        ancestors = set(node.node_ancestors())
        position = (node.lineno, node.col_offset)
        for other, parsed in _level_calls(node.frame()):
            if other is node or parsed.sets_debug:
                continue
            if (other.lineno, other.col_offset) >= position:
                continue
            if parsed.method == "set_level" or other.parent in ancestors:
                return True
        return False

    @staticmethod
    def _nested_in_other_level(node: nodes.Call) -> bool:
        """Return True when an enclosing function sets another level.

        The level a nested function starts at depends on when it is called,
        so any other level in an enclosing function counts.
        """
        frame = node.frame()
        while not isinstance(frame.parent, (nodes.Module, nodes.ClassDef)):
            frame = frame.parent.frame()
            if any(not parsed.sets_debug for _, parsed in _level_calls(frame)):
                return True
        return False

    @staticmethod
    def _block_sets_other_level(node: nodes.Call, call: _LevelCall) -> bool:
        """Return True when a DEBUG block's body calls ``set_level``.

        ``at_level`` restores the level on exit, so without the block a
        ``set_level`` with another level in its body would stay in effect
        after it.
        """
        if call.method != "at_level" or not isinstance(node.parent, nodes.With):
            return False
        return any(
            parsed.method == "set_level" and not parsed.sets_debug
            for statement in node.parent.body
            for _, parsed in _level_calls(statement)
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(RedundantCaplogLevelChecker(linter))
