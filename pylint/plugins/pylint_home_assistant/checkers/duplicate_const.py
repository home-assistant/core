"""Checker for integration constants that duplicate homeassistant.const.

When an integration defines a constant like ``CONF_HOST = "host"`` or
``CONF_HOST: Final = "host"`` that already exists with the same name
and value in ``homeassistant.const``, the integration should import it
instead of redefining it.
"""

import astroid
from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.helpers.module_info import is_integration_module

_ha_consts: dict[str, str] | None = None


def _load_ha_consts() -> dict[str, str]:
    """Load string constants from homeassistant.const.

    Returns a dict mapping constant name to its string value.
    Collects both annotated (``NAME: Final = "value"``) and plain
    (``NAME = "value"``) assignment forms.
    """
    global _ha_consts  # noqa: PLW0603
    if _ha_consts is not None:
        return _ha_consts

    _ha_consts = {}
    try:
        module = astroid.MANAGER.ast_from_module_name("homeassistant.const")
    except astroid.exceptions.AstroidBuildingError:
        return _ha_consts

    for item in module.body:
        name: str | None = None
        value_node: nodes.NodeNG | None = None

        if isinstance(item, nodes.AnnAssign) and isinstance(
            item.target, nodes.AssignName
        ):
            name = item.target.name
            value_node = item.value
        elif isinstance(item, nodes.Assign) and len(item.targets) == 1:
            target = item.targets[0]
            if isinstance(target, nodes.AssignName):
                name = target.name
                value_node = item.value

        if (
            name is not None
            and isinstance(value_node, nodes.Const)
            and isinstance(value_node.value, str)
        ):
            _ha_consts[name] = value_node.value

    return _ha_consts


def _check_assignment(
    checker: DuplicateConstChecker,
    node: nodes.NodeNG,
    name: str,
    value_node: nodes.NodeNG | None,
) -> None:
    """Check a single assignment for duplicate constants."""
    if not isinstance(node.parent, nodes.Module):
        return

    if value_node is None:
        return

    if not isinstance(value_node, nodes.Const):
        return

    if not isinstance(value_node.value, str):
        return

    ha_consts = _load_ha_consts()
    if name in ha_consts and ha_consts[name] == value_node.value:
        checker.add_message(
            "home-assistant-duplicate-const",
            node=node,
            args=(name,),
        )


class DuplicateConstChecker(BaseChecker):
    """Checker for constants that duplicate homeassistant.const entries."""

    name = "home_assistant_duplicate_const"
    priority = -1
    msgs = {
        "C7413": (
            "'%s' is already defined in homeassistant.const with the same "
            "value, import it instead of redefining it",
            "home-assistant-duplicate-const",
            "Used when an integration defines a constant that already exists "
            "with the same name and value in homeassistant.const.",
        ),
    }
    options = ()

    _in_integration: bool

    def visit_module(self, node: nodes.Module) -> None:
        """Track whether we are in an integration module."""
        self._in_integration = is_integration_module(node.name)

    def visit_assign(self, node: nodes.Assign) -> None:
        """Check plain assignments like ``NAME = 'value'``."""
        if not self._in_integration:
            return

        if len(node.targets) != 1:
            return

        target = node.targets[0]
        if not isinstance(target, nodes.AssignName):
            return

        _check_assignment(self, node, target.name, node.value)

    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        """Check annotated assignments like ``NAME: Final = 'value'``."""
        if not self._in_integration:
            return

        if not isinstance(node.target, nodes.AssignName):
            return

        _check_assignment(self, node, node.target.name, node.value)


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(DuplicateConstChecker(linter))
