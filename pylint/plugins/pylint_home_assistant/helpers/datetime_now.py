"""Shared logic for the ``datetime.now`` enforcement checkers.

The ``home-assistant-enforce-now``, ``home-assistant-enforce-utcnow`` and
``home-assistant-enforce-naive-now`` checkers all look for
``datetime.datetime.now(...)`` calls and differ only in which call shape they
care about. The common detection lives here; each checker module declares its
message and which case it fires on:

- ``utc``: ``datetime.now(UTC)`` -- steered to ``dt_util.utcnow``.
- ``other``: ``datetime.now(<non-UTC tz>)`` -- steered to ``dt_util.now``.
- ``naive``: ``datetime.now()`` with no time zone -- steered to
  ``dt_util.naive_now``.
"""

from astroid import nodes
from pylint.checkers import BaseChecker

# ``homeassistant.util.dt`` defines ``now``/``utcnow``/``naive_now`` itself, so
# it must call ``datetime.datetime.now(...)`` directly.
SKIP_MODULES = frozenset({"homeassistant.util.dt"})

# The mutually exclusive cases a ``datetime.now(...)`` call can fall into.
CASE_NAIVE = "naive"
CASE_UTC = "utc"
CASE_OTHER = "other"


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
    - ``flagged_case``: which call shape to fire on -- one of ``CASE_UTC``,
      ``CASE_OTHER`` or ``CASE_NAIVE``.
    """

    priority = -1
    options = ()

    message: str
    flagged_case: str

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
                    # ``datetime`` and exposes the ``datetime`` module as ``dt``
                    # (via ``import datetime as dt``), so ``dt_util.UTC`` and
                    # ``dt_util.dt.datetime.now(...)`` must be flagged too.
                    for name, alias in names:
                        if name == "dt":
                            local = alias or name
                            self._utc_paths.add((local, "UTC"))
                            self._datetime_class_paths.add((local, "dt", "datetime"))
                case nodes.ImportFrom(modname="homeassistant.util.dt", names=names):
                    for name, alias in names:
                        match name:
                            case "UTC":
                                self._utc_paths.add((alias or name,))
                            case "dt":
                                # ``from homeassistant.util.dt import dt`` binds
                                # the ``datetime`` module directly.
                                self._datetime_class_paths.add(
                                    (alias or name, "datetime")
                                )
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
                                self._datetime_class_paths.add(
                                    (alias, "dt", "datetime")
                                )

    def visit_call(self, node: nodes.Call) -> None:
        """Check for ``datetime.now(...)`` calls matching the configured case."""
        if not self._enabled:
            return

        match node:
            case nodes.Call(
                func=nodes.Attribute(attrname="now", expr=expr),
                args=[],
                keywords=[],
            ):
                arg = None
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
        if self._categorize(arg) != self.flagged_case:
            return

        self.add_message(self.message, node=node)

    def _categorize(self, arg: nodes.NodeNG | None) -> str:
        """Categorize the time zone argument of a ``datetime.now(...)`` call.

        A missing argument or an explicit ``None`` yields a naive ``datetime``.
        """
        if arg is None or (isinstance(arg, nodes.Const) and arg.value is None):
            return CASE_NAIVE
        if attribute_path(arg) in self._utc_paths or is_zoneinfo_utc(arg):
            return CASE_UTC
        return CASE_OTHER
