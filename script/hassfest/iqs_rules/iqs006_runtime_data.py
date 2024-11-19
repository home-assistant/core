"""Enforce that the integration only uses ConfigEntry.runtime_data and not hass.data."""

import ast

from script.hassfest.model import Integration


def validate(integration: Integration) -> None:
    """Validate that the integration does not use hass.data."""

    # Walk all files in the integration and check for hass.data
    for file in integration.path.rglob("*.py"):
        tree = ast.parse(file.read_text())

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "hass"
                and node.attr == "data"
            ):
                integration.add_error(
                    "IQS006",
                    "Integration is using hass.data, use ConfigEntry.runtime_data instead",
                )
                return
