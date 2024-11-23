"""Validates that the configuration only uses Use ConfigEntry.runtime_data to store runtime data."""

import ast

from . import QualityScaleCheck


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration does not use hass.data."""

    # Walk all files in the integration and check for hass.data
    for file in check.integration.path.rglob("*.py"):
        tree = ast.parse(file.read_text())

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "hass"
                and node.attr == "data"
            ):
                check.add_error(
                    "runtime_data",
                    "Integration is not using ConfigEntry runtime_data (found use of hass.data "
                    "in {file})",
                )
                return
