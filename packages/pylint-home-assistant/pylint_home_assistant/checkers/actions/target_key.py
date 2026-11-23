"""Checker for the target keys of action calls.

Target keys select what an action applies to, so they use ``TargetKey``.
Only ``hass.services.async_call`` calls are checked: every constant key of
their ``target=`` dict literal is a target key, and so is every constant key of
its ``exclude`` dict literal.

In tests, the ``entity_id`` key of their data dict literal is checked too, when
the action is a ``<Prefix>Service`` enum member which declares a ``target`` in
its ``services.yaml``.

- ``C7465``: Target key of an action call should use ``TargetKey``
"""

from functools import cache
from pathlib import Path
import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.checkers.utils import safe_infer
from pylint.lint import PyLinter
import yaml

from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import is_test_module

_ENTITY_ID_KEYS = {
    "ATTR_ENTITY_ID",
    "CONF_ENTITY_ID",
    "CommonServiceArgument.ENTITY_ID",
}

# Constant keys of a target dict, with the TargetKey member they stand for
_TARGET_KEY = re.compile(
    r"(?:ATTR|CONF)_(ENTITY|DEVICE|AREA|FLOOR|LABEL)_ID"
    r"|CommonServiceArgument\.(ENTITY|DEVICE)_ID"
)


@cache
def _target_actions(integration_dir: Path) -> set[str]:
    """Return the actions of an integration which declare a target."""
    try:
        content = (integration_dir / "services.yaml").read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    return {
        name
        for name, spec in (yaml.safe_load(content) or {}).items()
        if isinstance(spec, dict) and "target" in spec
    }


def _declares_target(action: nodes.NodeNG) -> bool:
    """Check if an action is an enum member which declares a target."""
    match action:
        case nodes.Attribute(expr=nodes.Name(name=name) as expr, attrname=member) if (
            name.endswith("Service")
        ):
            pass
        case _:
            return False
    enum_class = safe_infer(expr)
    if not isinstance(enum_class, nodes.ClassDef) or not (
        definitions := enum_class.locals.get(member)
    ):
        return False
    integration_dir = get_integration_dir(enum_class.root())
    match definitions[0].parent:
        case nodes.Assign(value=nodes.Const(value=str() as value)) if integration_dir:
            return value in _target_actions(integration_dir)
    return False


def _is_async_call(node: nodes.Call) -> bool:
    """Check if a call is ``<...>.services.async_call(...)``."""
    func = node.func
    return (
        isinstance(func, nodes.Attribute)
        and func.attrname == "async_call"
        and isinstance(func.expr, nodes.Attribute)
        and func.expr.attrname == "services"
    )


def _is_exclude_key(key: nodes.NodeNG | None) -> bool:
    """Check if a target key is the key of the exclude block."""
    match key:
        case nodes.Name(name="CONF_EXCLUDE") | nodes.Const(value="exclude"):
            return True
    return False


def _keyword_value(node: nodes.Call, name: str) -> nodes.NodeNG | None:
    """Return the value of a keyword argument of a call."""
    for keyword in node.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def _argument(node: nodes.Call, position: int, name: str) -> nodes.NodeNG | None:
    """Return an argument of a call, passed by position or by keyword."""
    if len(node.args) > position:
        return node.args[position]
    return _keyword_value(node, name)


class TargetKeyChecker(BaseChecker):
    """Checker for the target keys of action calls."""

    name = "home_assistant_target_key"
    priority = -1
    msgs = {
        "C7465": (
            "Target key %s should be %s",
            "home-assistant-action-target-key",
            "Used when the target dict of an action call, or in tests the data "
            "dict of an action which declares a target, uses a constant other "
            "than TargetKey as target key. Target keys select what the "
            "action applies to, not fields of the action, so they use TargetKey.",
        ),
    }
    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Visit Module node."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Check the target keys of hass.services.async_call."""
        if not _is_async_call(node):
            return
        target = _keyword_value(node, "target")
        if isinstance(target, nodes.Dict):
            self._check_target(target)
        if self._in_test_module:
            self._check_data(node)

    def _check_data(self, node: nodes.Call) -> None:
        """Report the entity_id key of the data of an action with a target."""
        action = _argument(node, 1, "service")
        data = _argument(node, 2, "service_data")
        if action is None or not isinstance(data, nodes.Dict):
            return
        keys = [key for key, _ in data.items if key.as_string() in _ENTITY_ID_KEYS]
        if not keys or not _declares_target(action):
            return
        for key in keys:
            self._report(key, "TargetKey.ENTITY_ID")

    def _check_target(self, target: nodes.Dict) -> None:
        """Report constant keys of a target dict and of its exclude dict."""
        for key, value in target.items:
            if _is_exclude_key(key) and isinstance(value, nodes.Dict):
                self._check_target(value)
                continue
            if not isinstance(key, (nodes.Name, nodes.Attribute)):
                continue
            if match := _TARGET_KEY.fullmatch(key.as_string()):
                self._report(key, f"TargetKey.{match[1] or match[2]}_ID")

    def _report(self, key: nodes.NodeNG, replacement: str) -> None:
        """Report a target key which should use TargetKey."""
        self.add_message(
            "home-assistant-action-target-key",
            node=key,
            args=(key.as_string(), replacement),
        )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(TargetKeyChecker(linter))
