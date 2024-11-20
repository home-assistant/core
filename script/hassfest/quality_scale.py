"""Validate integration quality scale files."""

from __future__ import annotations

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration

RULES = [
    "action-exceptions",
    "action-setup",
    "appropriate-polling",
    "async-dependency",
    "brands",
    "common-modules",
    "config-entry-unloading",
    "config-flow",
    "config-flow-test-coverage",
    "dependency-transparency",
    "devices",
    "diagnostics",
    "discovery",
    "discovery-update-info",
    "docs-actions",
    "docs-configuration-parameters",
    "docs-data-update",
    "docs-examples",
    "docs-high-level-description",
    "docs-installation-instructions",
    "docs-installation-parameters",
    "docs-known-limitations",
    "docs-removal-instructions",
    "docs-supported-devices",
    "docs-supported-functions",
    "docs-troubleshooting",
    "docs-use-cases",
    "dynamic-devices",
    "entity-category",
    "entity-device-class",
    "entity-disabled-by-default",
    "entity-event-setup",
    "entity-translations",
    "entity-unavailable",
    "entity-unique-id",
    "exception-translations",
    "has-entity-name",
    "icon-translations",
    "inject-websession",
    "integration-owner",
    "log-when-unavailable",
    "parallel-updates",
    "reauthentication-flow",
    "reconfiguration-flow",
    "repair-issues",
    "runtime-data",
    "stale-devices",
    "strict-typing",
    "test-before-configure",
    "test-before-setup",
    "test-coverage",
    "unique-config-entry",
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
