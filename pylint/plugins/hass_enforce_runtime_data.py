"""Plugin for enforcing runtime_data over hass.data[DOMAIN].

New integrations should store per-entry data on ``entry.runtime_data`` (typed
via a ``type`` alias) rather than the legacy ``hass.data[DOMAIN][entry.entry_id]``
dictionary pattern. The ``runtime_data`` approach is type-safe, automatically
cleaned up on unload, and is the current Home Assistant core standard.

Using ``hass.data[DOMAIN]`` was the #2 most common review comment across 1,100+
pull requests reviewed (69 occurrences), making it a high-value target for
automated enforcement.
"""

from __future__ import annotations

from pathlib import Path

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

_SKIP_MODULES: set[str] = {
    "application_credentials",
    "config_flow",
    "const",
    "diagnostics",
}

_SKIP_FUNCTIONS: set[str] = {
    "async_migrate_entry",
    "async_remove_entry",
    "async_unload_entry",
}


_has_config_flow_cache: dict[str, bool] = {}


class HassEnforceRuntimeDataChecker(BaseChecker):
    """Checker for runtime_data usage."""

    name = "hass_enforce_runtime_data"
    priority = -1
    msgs = {
        "W7482": (
            "Use entry.runtime_data instead of hass.data[DOMAIN] "
            "(https://developers.home-assistant.io/docs/core/"
            "integration-quality-scale/rules/runtime-data)",
            "hass-use-runtime-data",
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

        root_name = node.root().name
        if not root_name.startswith("homeassistant.components."):
            return

        parts = root_name.split(".")
        current_module = parts[3] if len(parts) > 3 else ""
        if current_module in _SKIP_MODULES:
            return

        # Only flag integrations that have a config flow (and thus can use
        # entry.runtime_data). YAML-only integrations legitimately need
        # hass.data[DOMAIN].
        integration = parts[2]
        if not _has_config_flow(integration, node.root()):
            return

        func = _enclosing_function(node)
        if func and func.name in _SKIP_FUNCTIONS:
            return

        # Don't flag deletion: del hass.data[DOMAIN] or hass.data[DOMAIN].pop(...)
        match node.parent:
            case nodes.Delete():
                return
            case nodes.Attribute(attrname="pop", parent=nodes.Call()):
                return

        self.add_message("hass-use-runtime-data", node=node)


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


def _has_config_flow(integration: str, module: nodes.Module) -> bool:
    """Return True if the integration has a config_flow.py.

    Results are cached per integration domain. If the file path cannot be
    resolved (e.g. in tests), defaults to True so the checker still flags.
    """
    if integration in _has_config_flow_cache:
        return _has_config_flow_cache[integration]

    result = True  # default to flagging when path is unknown
    if module.file and module.file != "<?>":
        # Derive integration directory from the file path
        file_path = Path(module.file)
        # Walk up to the integration directory (homeassistant/components/<domain>/)
        for parent in (file_path.parent, *file_path.parents):
            if parent.parent.name == "components":
                result = (parent / "config_flow.py").exists()
                break

    _has_config_flow_cache[integration] = result
    return result


def _enclosing_function(node: nodes.NodeNG) -> nodes.FunctionDef | None:
    """Walk up the tree to find the enclosing function."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.FunctionDef):
            return current
        current = current.parent
    return None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceRuntimeDataChecker(linter))
