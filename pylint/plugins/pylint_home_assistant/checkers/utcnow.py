"""Checker that enforces ``homeassistant.util.dt.utcnow`` over ``datetime.now(UTC)``.

Home Assistant exposes ``homeassistant.util.dt.utcnow`` -- a thin wrapper around
``datetime.datetime.now(UTC)`` implemented as a ``functools.partial``. Using the
helper avoids the per-call global lookup of ``UTC`` and keeps the codebase
consistent in how the current UTC time is obtained.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

# ``homeassistant.util.dt`` defines ``utcnow`` itself, so it must call
# ``datetime.datetime.now(UTC)`` directly.
_SKIP_MODULES = frozenset({"homeassistant.util.dt"})


def _attribute_path(node: nodes.NodeNG) -> tuple[str, ...] | None:
    """Return the dotted-name path of an Attribute/Name chain, or ``None``."""
    parts: list[str] = []
    while isinstance(node, nodes.Attribute):
        parts.append(node.attrname)
        node = node.expr
    if not isinstance(node, nodes.Name):
        return None
    parts.append(node.name)
    return tuple(reversed(parts))


class HassEnforceUtcnowChecker(BaseChecker):
    """Checker that flags ``datetime.now(UTC)`` calls."""

    name = "home_assistant_enforce_utcnow"
    priority = -1
    msgs = {
        "C7414": (
            "Use `homeassistant.util.dt.utcnow()` instead of `datetime.now(UTC)`",
            "home-assistant-enforce-utcnow",
            "Used when ``datetime.datetime.now(UTC)`` is called. Use the "
            "``homeassistant.util.dt.utcnow`` helper instead -- it is "
            "implemented as ``functools.partial(datetime.datetime.now, UTC)`` "
            "and avoids the global lookup of ``UTC`` on every call.",
        ),
    }
    options = ()

    _enabled: bool
    _datetime_class_paths: set[tuple[str, ...]]
    _utc_paths: set[tuple[str, ...]]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect ``datetime`` bindings introduced by module-level imports."""
        self._datetime_class_paths = set()
        self._utc_paths = set()
        self._enabled = node.name not in _SKIP_MODULES
        if not self._enabled:
            return

        for stmt in node.body:
            if isinstance(stmt, nodes.ImportFrom):
                if stmt.modname != "datetime":
                    continue
                for name, alias in stmt.names:
                    local = alias or name
                    if name == "datetime":
                        self._datetime_class_paths.add((local,))
                    elif name == "UTC":
                        self._utc_paths.add((local,))
                    elif name == "timezone":
                        self._utc_paths.add((local, "utc"))
            elif isinstance(stmt, nodes.Import):
                for name, alias in stmt.names:
                    if name != "datetime":
                        continue
                    local = alias or name
                    self._datetime_class_paths.add((local, "datetime"))
                    self._utc_paths.add((local, "UTC"))
                    self._utc_paths.add((local, "timezone", "utc"))

    def visit_call(self, node: nodes.Call) -> None:
        """Check for ``datetime.now(UTC)`` calls."""
        if not self._enabled:
            return

        if not isinstance(node.func, nodes.Attribute):
            return
        if node.func.attrname != "now":
            return
        if len(node.args) != 1 or node.keywords:
            return

        expr_path = _attribute_path(node.func.expr)
        if expr_path is None or expr_path not in self._datetime_class_paths:
            return

        arg_path = _attribute_path(node.args[0])
        if arg_path is None or arg_path not in self._utc_paths:
            return

        self.add_message("home-assistant-enforce-utcnow", node=node)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceUtcnowChecker(linter))
