"""Validate integration quality scale files."""

from __future__ import annotations

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration

RULES = [
    "action_exceptions",
    "action_setup",
    "appropriate_polling",
    "async_dependency",
    "brands",
    "common_modules",
    "config_entry_unloading",
    "config_flow",
    "config_flow_test_coverage",
    "dependency_transparency",
    "devices",
    "diagnostics",
    "discovery",
    "discovery_update_info",
    "docs_actions",
    "docs_configuration_parameters",
    "docs_data_update",
    "docs_examples",
    "docs_high_level_description",
    "docs_installation_instructions",
    "docs_installation_parameters",
    "docs_known_limitations",
    "docs_removal_instructions",
    "docs_supported_devices",
    "docs_supported_functions",
    "docs_troubleshooting",
    "docs_use_cases",
    "dynamic_devices",
    "entity_category",
    "entity_device_class",
    "entity_disabled_by_default",
    "entity_event_setup",
    "entity_translations",
    "entity_unavailable",
    "entity_unique_id",
    "exception_translations",
    "has_entity_name",
    "icon_translations",
    "inject_websession",
    "integration_owner",
    "log_when_unavailable",
    "parallel_updates",
    "reauthentication_flow",
    "reconfiguration_flow",
    "repair_issues",
    "runtime_data",
    "stale_devices",
    "strict_typing",
    "test_before_configure",
    "test_before_setup",
    "test_coverage",
    "unique_config_entry",
]

SCHEMA = vol.Schema(
    {
        vol.Required("rules"): vol.Schema(
            {
                vol.Optional(rule): vol.Any(
                    vol.In(["todo", "done"]),
                    vol.Schema(
                        {
                            vol.Required("status"): vol.In(["todo", "done", "exempt"]),
                            vol.Optional("comment"): str,
                        }
                    ),
                )
                for rule in RULES
            }
        )
    }
)


def validate_iqs_file(config: Config, integration: Integration) -> None:
    """Validate quality scale file for integration."""
    iqs_file = integration.path / "quality_scale.yaml"
    if not iqs_file.is_file():
        return

    name = str(iqs_file)

    try:
        data = load_yaml_dict(name)
    except HomeAssistantError:
        integration.add_error("quality_scale", "Invalid quality_scale.yaml")
        return

    try:
        SCHEMA(data)
    except vol.Invalid as err:
        integration.add_error(
            "quality_scale", f"Invalid {name}: {humanize_error(data, err)}"
        )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Handle YAML files inside integrations."""
    for integration in integrations.values():
        validate_iqs_file(config, integration)
