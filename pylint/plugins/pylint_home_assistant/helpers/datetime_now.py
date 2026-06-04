"""Shared logic for the ``datetime.now`` enforcement checkers.

Both the ``home-assistant-enforce-now`` and ``home-assistant-enforce-utcnow``
checkers look for ``datetime.datetime.now(<tz>)`` calls and differ only in which
time zone argument they care about. The common detection lives here; each checker
module just declares its message and whether it fires on the UTC case.
"""

from astroid import nodes
from pylint.checkers import BaseChecker

# ``homeassistant.util.dt`` defines ``now``/``utcnow`` itself, so it must call
# ``datetime.datetime.now(...)`` directly.
SKIP_MODULES = frozenset({"homeassistant.util.dt"})


def attribute_path(node: nodes.NodeNG) -> tuple[str, ...] | None:
    """Return the dotted-name path of an Attribute/Name chain, or ``None``."""
    parts: list[str] = []
    while isinstance(node, nodes.Attribute):
        parts.append(node.attrname)
        node = node.expr
    if not isinstance(node, nodes.Name):
        return None
    parts.append(node.name)
    return tuple(reversed(parts))


def is_zoneinfo_utc(node: nodes.NodeNG) -> bool:
    """Return True if *node* is ``ZoneInfo("UTC")`` or ``*.ZoneInfo("UTC")``."""
    match node:
        case nodes.Call(
            func=nodes.Name(name="ZoneInfo") | nodes.Attribute(attrname="ZoneInfo"),
            args=[nodes.Const(value="UTC")],
            keywords=[],
        ):
            return True
    return False


class HassEnforceDatetimeNowChecker(BaseChecker):
    """Base checker for ``datetime.datetime.now(<tz>)`` calls.

    Subclasses must define ``name`` and ``msgs`` and set:

    - ``message``: the message symbol to emit.
    - ``flags_utc``: ``True`` to fire on the UTC case, ``False`` to fire on every
      other (non-UTC) time zone.
    """

    priority = -1
    options = ()

    message: str
    flags_utc: bool

    _enabled: bool
    _datetime_class_paths: set[tuple[str, ...]]
    _utc_paths: set[tuple[str, ...]]

    def visit_module(self, node: nodes.Module) -> None:
        """Collect ``datetime`` bindings introduced by module-level imports."""
        self._datetime_class_paths = set()
        self._utc_paths = set()
        self._enabled = node.name not in SKIP_MODULES
        if not self._enabled:
            return

        for stmt in node.body:
            match stmt:
                case nodes.ImportFrom(modname="datetime", names=names):
                    for name, alias in names:
                        local = alias or name
                        match name:
                            case "datetime":
                                self._datetime_class_paths.add((local,))
                            case "UTC":
                                self._utc_paths.add((local,))
                            case "timezone":
                                self._utc_paths.add((local, "utc"))
                case nodes.ImportFrom(modname="homeassistant.util", names=names):
                    # ``homeassistant.util.dt`` re-exports ``UTC`` from
                    # ``datetime``, so ``dt_util.UTC`` must be flagged too.
                    for name, alias in names:
                        if name == "dt":
                            local = alias or name
                            self._utc_paths.add((local, "UTC"))
                case nodes.ImportFrom(modname="homeassistant.util.dt", names=names):
                    for name, alias in names:
                        if name == "UTC":
                            self._utc_paths.add((alias or name,))
                case nodes.Import(names=names):
                    for name, alias in names:
                        match name:
                            case "datetime":
                                local = alias or name
                                self._datetime_class_paths.add((local, "datetime"))
                                self._utc_paths.add((local, "UTC"))
                                self._utc_paths.add((local, "timezone", "utc"))
                            case "homeassistant.util.dt" if alias:
                                self._utc_paths.add((alias, "UTC"))

    def visit_call(self, node: nodes.Call) -> None:
        """Check for ``datetime.now(<tz>)`` calls matching the configured case."""
        if not self._enabled:
            return

        match node:
            case nodes.Call(
                func=nodes.Attribute(attrname="now", expr=expr),
                args=[arg],
                keywords=[],
            ):
                pass
            case nodes.Call(
                func=nodes.Attribute(attrname="now", expr=expr),
                args=[],
                keywords=[nodes.Keyword(arg="tz", value=arg)],
            ):
                pass
            case _:
                return

        if attribute_path(expr) not in self._datetime_class_paths:
            return
        is_utc = attribute_path(arg) in self._utc_paths or is_zoneinfo_utc(arg)
        if is_utc is not self.flags_utc:
            return

        self.add_message(self.message, node=node)
