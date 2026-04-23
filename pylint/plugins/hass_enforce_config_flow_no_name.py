"""Plugin for detecting name fields in config flow schemas.

Config flows should not ask users to provide a name for the device or
integration entry. The name is either automatically derived from the
device (via discovery) or from the integration's manifest. Letting users
set names leads to inconsistency and is a common review comment on new
integration PRs.

Found in 7.6% of new-integration PRs across 1,100+ analyzed PRs, April 2026.
"""

from __future__ import annotations

import json
from pathlib import Path

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.lint import PyLinter

# Field names that indicate a "name" field in a config flow schema.
_NAME_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "CONF_DEVICE_NAME",
        "CONF_NAME",
        "device_name",
        "name",
    }
)


_is_helper_cache: dict[str, bool] = {}


class HassEnforceConfigFlowNoNameChecker(BaseChecker):
    """Checker for name fields in config flow schemas.

    Config flows should not include name fields (CONF_NAME, "name") -- names
    come from discovery or the integration manifest.
    """

    name = "hass_enforce_config_flow_no_name"
    priority = -1
    msgs = {
        "W7493": (
            "Config flow should not include a '%s' field -- names are derived "
            "from discovery or the integration manifest",
            "hass-config-flow-name-field",
            "Used when a config flow schema includes a name field. Users "
            "should not set names in config flows; they come automatically "
            "from the device (via discovery) or the integration manifest.",
        ),
    }
    options = ()

    def visit_call(self, node: nodes.Call) -> None:
        """Check for name fields in vol.Required/Optional calls."""
        root_name = node.root().name
        if not root_name.startswith("homeassistant.components."):
            return

        parts = root_name.split(".")
        current_module = parts[3] if len(parts) > 3 else ""
        if current_module != "config_flow":
            return

        # Helper integrations legitimately ask users for a name since there
        # is no device to discover the name from.
        integration = parts[2]
        if _is_helper_integration(integration, node.root()):
            return

        # Subentry flows may legitimately ask for a name.
        if _is_in_subentry_flow(node):
            return

        field_name = _get_schema_field_name(node)
        if field_name is None:
            return

        if field_name in _NAME_FIELD_NAMES:
            self.add_message(
                "hass-config-flow-name-field",
                node=node,
                args=(field_name,),
            )


def _is_helper_integration(integration: str, module: nodes.Module) -> bool:
    """Return True if the integration has integration_type 'helper'.

    Results are cached per integration domain. If the manifest cannot be
    read (e.g. in tests), defaults to False so the checker still flags.
    """
    if integration in _is_helper_cache:
        return _is_helper_cache[integration]

    result = False  # default to flagging when path is unknown
    if module.file and module.file != "<?>":
        file_path = Path(module.file)
        for parent in (file_path.parent, *file_path.parents):
            if parent.parent.name == "components":
                manifest = parent / "manifest.json"
                if manifest.exists():
                    try:
                        data = json.loads(manifest.read_text())
                        result = data.get("integration_type") == "helper"
                    except json.JSONDecodeError, OSError:
                        pass
                break

    _is_helper_cache[integration] = result
    return result


def _is_in_subentry_flow(node: nodes.NodeNG) -> bool:
    """Return True if the node is inside a ConfigSubentryFlow class."""
    current = node.parent
    while current is not None:
        if isinstance(current, nodes.ClassDef):
            for base in current.bases:
                if isinstance(base, nodes.Name) and "SubentryFlow" in base.name:
                    return True
                if (
                    isinstance(base, nodes.Attribute)
                    and "SubentryFlow" in base.attrname
                ):
                    return True
        current = current.parent
    return False


def _get_schema_field_name(node: nodes.Call) -> str | None:
    """Extract the field name from vol.Required(...) or vol.Optional(...)."""
    if not isinstance(node.func, nodes.Attribute):
        return None
    if node.func.attrname not in {"Required", "Optional"}:
        return None
    if not node.args:
        return None

    first_arg = node.args[0]
    if isinstance(first_arg, nodes.Const) and isinstance(first_arg.value, str):
        return first_arg.value
    if isinstance(first_arg, nodes.Name):
        return str(first_arg.name)
    return None


def register(linter: PyLinter) -> None:
    """Register the checker."""
    linter.register_checker(HassEnforceConfigFlowNoNameChecker(linter))
