"""Checker for the target keys in the data of action calls.

The ``entity_id`` of an action that declares a ``target`` in its
``services.yaml`` selects what the action applies to: it is a target key, not
a field of the action, so it uses ``TargetKey.ENTITY_ID``.
``CommonServiceArgument.ENTITY_ID`` is for actions with their own
``entity_id`` field.

Only ``hass.services.async_call`` calls in tests are checked whose action is
a ``<Prefix>Service`` enum member and whose data is a dict literal (positional
or ``service_data=``).

- ``C7465``: Target key of an action call should use ``TargetKey``
"""

from pathlib import Path

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter
import yaml

from pylint_home_assistant.helpers.integration import get_integration_dir
from pylint_home_assistant.helpers.module_info import is_test_module

_ENTITY_ID_KEYS = {
    "ATTR_ENTITY_ID",
    "CONF_ENTITY_ID",
    "CommonServiceArgument.ENTITY_ID",
}

# Actions declaring a target, keyed by integration directory
_target_actions_cache: dict[Path, set[str]] = {}


def clear_target_actions_cache() -> None:
    """Clear the services.yaml cache (used by tests)."""
    _target_actions_cache.clear()


def _target_actions(integration_dir: Path) -> set[str]:
    """Return the actions of an integration that declare a target."""
    if integration_dir not in _target_actions_cache:
        try:
            services = yaml.safe_load(
                (integration_dir / "services.yaml").read_text(encoding="utf-8")
            )
        except OSError, yaml.YAMLError:
            services = None
        _target_actions_cache[integration_dir] = {
            name
            for name, spec in (services or {}).items()
            if isinstance(spec, dict) and "target" in spec
        }
    return _target_actions_cache[integration_dir]


def _declares_target(action: nodes.NodeNG) -> bool:
    """Check if an action enum member is an action that declares a target."""
    if not isinstance(action, nodes.Attribute) or not isinstance(
        action.expr, nodes.Name
    ):
        return False
    if not action.expr.name.endswith("Service"):
        return False
    try:
        enum_class = next(action.expr.infer())
    except astroid.InferenceError, StopIteration:
        return False
    if not isinstance(enum_class, nodes.ClassDef):
        return False
    member = enum_class.locals.get(action.attrname)
    if not member or not isinstance(assign := member[0].parent, nodes.Assign):
        return False
    if not isinstance(assign.value, nodes.Const) or not isinstance(
        assign.value.value, str
    ):
        return False
    integration_dir = get_integration_dir(enum_class.root())
    if integration_dir is None:
        return False
    return assign.value.value in _target_actions(integration_dir)


def _is_async_call(node: nodes.Call) -> bool:
    """Check if a call is ``<...>.services.async_call(...)``."""
    func = node.func
    return (
        isinstance(func, nodes.Attribute)
        and func.attrname == "async_call"
        and isinstance(func.expr, nodes.Attribute)
        and func.expr.attrname == "services"
    )


def _call_data(node: nodes.Call) -> nodes.NodeNG | None:
    """Return the data argument of an action call."""
    if len(node.args) >= 3:
        return node.args[2]
    for keyword in node.keywords:
        if keyword.arg == "service_data":
            return keyword.value
    return None


class TargetKeyChecker(BaseChecker):
    """Checker for the target keys in the data of action calls."""

    name = "home_assistant_target_key"
    priority = -1
    msgs = {
        "C7465": (
            "Target key %s should be TargetKey.ENTITY_ID",
            "home-assistant-action-target-key",
            "Used when the data of an action call in a test uses ATTR_ENTITY_ID, "
            "CONF_ENTITY_ID or CommonServiceArgument.ENTITY_ID as key, and the "
            "action declares a target in its services.yaml. The entity_id of "
            "such an action is a target key, not a field of the action, so it "
            "uses TargetKey.ENTITY_ID.",
        ),
    }
    options = ()

    _in_test_module: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Only check test modules."""
        self._in_test_module = is_test_module(node.name)

    def visit_call(self, node: nodes.Call) -> None:
        """Check the data keys of hass.services.async_call."""
        if not self._in_test_module or not _is_async_call(node) or len(node.args) < 2:
            return
        data = _call_data(node)
        if not isinstance(data, nodes.Dict):
            return
        keys = [
            key
            for key, _ in data.items
            if isinstance(key, (nodes.Name, nodes.Attribute))
            and key.as_string() in _ENTITY_ID_KEYS
        ]
        if not keys or not _declares_target(node.args[1]):
            return
        for key in keys:
            self.add_message(
                "home-assistant-action-target-key",
                node=key,
                args=(key.as_string(),),
            )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(TargetKeyChecker(linter))
