"""Checker for enforcing runtime_data over hass.data[DOMAIN].

New integrations should store per-entry data on ``entry.runtime_data`` (typed
via a ``type`` alias) rather than the legacy ``hass.data[DOMAIN][entry.entry_id]``
dictionary pattern. The ``runtime_data`` approach is type-safe, automatically
cleaned up on unload, and is the current Home Assistant core standard.
"""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

from pylint_home_assistant.const import Module
from pylint_home_assistant.helpers.ast_utils import enclosing_function
from pylint_home_assistant.helpers.integration import has_config_flow
from pylint_home_assistant.helpers.module_info import parse_module

_SKIP_MODULES: set[str] = {
    Module.APPLICATION_CREDENTIALS,
    Module.CONFIG_FLOW,
    Module.CONST,
    Module.DIAGNOSTICS,
}

_SKIP_FUNCTIONS: set[str] = {
    "async_migrate_entry",
    "async_remove_entry",
    "async_unload_entry",
}


class HassEnforceRuntimeDataChecker(BaseChecker):
    """Checker for runtime_data usage."""

    name = "home_assistant_enforce_runtime_data"
    priority = -1
    msgs = {
        "W7405": (
            "Use entry.runtime_data instead of hass.data[DOMAIN] "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/runtime-data)",
            "home-assistant-use-runtime-data",
            "Used when integration code accesses hass.data[DOMAIN]. "
            "New integrations should use entry.runtime_data for type-safe, "
            "automatically-cleaned-up per-entry data storage. "
            "See https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/runtime-data",
        ),
    }
    options = ()

    def visit_subscript(self, node: nodes.Subscript) -> None:
        """Check for hass.data[DOMAIN] access."""
        if not _is_hass_data_domain_access(node):
            return

        parsed = parse_module(node.root().name)
        if parsed is None:
            return

        current_module = parsed.module or ""
        if current_module in _SKIP_MODULES:
            return

        # Only flag integrations that have a config flow (and thus can use
        # entry.runtime_data). YAML-only integrations legitimately need
        # hass.data[DOMAIN].
        if not has_config_flow(parsed.domain, node.root()):
            return

        func = enclosing_function(node)
        if func and func.name in _SKIP_FUNCTIONS:
            return

        # Don't flag deletion: del hass.data[DOMAIN] or hass.data[DOMAIN].pop(...)
        match node.parent:
            case nodes.Delete():
                return
            case nodes.Attribute(attrname="pop", parent=nodes.Call()):
                return

        self.add_message("home-assistant-use-runtime-data", node=node)


def _is_hass_data_domain_access(node: nodes.Subscript) -> bool:
    """Return True if node is hass.data[DOMAIN] or self.hass.data[DOMAIN]."""
    match node:
        case nodes.Subscript(
            value=nodes.Attribute(
                expr=(
                    nodes.Name(name="hass")
                    | nodes.Attribute(expr=nodes.Name(name="self"), attrname="hass")
                ),
                attrname="data",
            ),
            slice=nodes.Name(name="DOMAIN"),
        ):
            return True
        case _:
            return False


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceRuntimeDataChecker(linter))
