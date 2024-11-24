"""Enforce that the integration only uses ConfigEntry.runtime_data and not hass.data."""

import ast

from . import QualityScaleCheck


def validate(check: QualityScaleCheck) -> None:
    """Validate that the integration does not use hass.data."""

    # Walk all files in the integration and check for hass.data
    for root, _dirs, files in check.integration.path.walk():
        for file in files:
            if not file.endswith(".py"):
                continue
            file_path = root / file
            tree = ast.parse(file_path.read_text())

            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "hass"
                    and node.attr == "data"
                ):
                    check.add_error(
                        "runtime-data",
                        "Integration is not exclusively using ConfigEntry.runtime_data "
                        f"(found use of hass.data in {file_path}). You may add an exemption if using "
                        "hass.data for global storage not specific to a config entry.)",
                    )
                    break
