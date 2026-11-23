"""Checker for the target keys of action calls.

Target keys select what an action applies to, so they use ``TargetKey``.
Only ``hass.services.async_call`` calls are checked: every constant key of
their ``target=`` dict literal is a target key, and so is every constant key of
its ``exclude`` dict literal.

- ``C7465``: Target key of an action call should use ``TargetKey``
"""

import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

# Constant keys of a target dict, with the TargetKey member they stand for
_TARGET_KEY = re.compile(
    r"(?:ATTR|CONF)_(ENTITY|DEVICE|AREA|FLOOR|LABEL)_ID"
    r"|CommonServiceArgument\.(ENTITY|DEVICE)_ID"
)


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


class TargetKeyChecker(BaseChecker):
    """Checker for the target keys of action calls."""

    name = "home_assistant_target_key"
    priority = -1
    msgs = {
        "C7465": (
            "Target key %s should be %s",
            "home-assistant-action-target-key",
            "Used when the target dict of an action call uses a constant "
            "other than TargetKey as key. Target keys select what the "
            "action applies to, not fields of the action, so they use TargetKey.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check the target keys of hass.services.async_call."""
        if not _is_async_call(node):
            return
        target = _keyword_value(node, "target")
        if isinstance(target, nodes.Dict):
            self._check_target(target)

    def _check_target(self, target: nodes.Dict) -> None:
        """Report constant keys of a target dict and of its exclude dict."""
        for key, value in target.items:
            if _is_exclude_key(key) and isinstance(value, nodes.Dict):
                self._check_target(value)
                continue
            if not isinstance(key, (nodes.Name, nodes.Attribute)):
                continue
            if match := _TARGET_KEY.fullmatch(key.as_string()):
                self.add_message(
                    "home-assistant-action-target-key",
                    node=key,
                    args=(key.as_string(), f"TargetKey.{match[1] or match[2]}_ID"),
                )


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(TargetKeyChecker(linter))
