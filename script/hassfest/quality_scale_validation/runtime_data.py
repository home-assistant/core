"""Enforce that the integration only uses ConfigEntry.runtime_data.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data
"""

import ast
from collections.abc import Generator
import pathlib

from script.hassfest.model import Integration


def _integration_python_files(
    integration: Integration,
) -> Generator[pathlib.Path, None, None]:
    """Return all python files in the integration."""
    for root, _dirs, files in integration.path.walk():
        for file in files:
            if file.endswith(".py"):
                yield root / file


def _has_hass_data(tree: ast.Module) -> bool:
    """Test if the module uses hass.data."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "hass"
            and node.attr == "data"
        ):
            return True
    return False


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration does not use hass.data."""
    errors = []
    for file_path in _integration_python_files(integration):
        module = ast.parse(file_path.read_text())
        if _has_hass_data(module):
            errors.append(
                "Integration is not exclusively using ConfigEntry.runtime_data "
                f"(found use of hass.data in {file_path}). You may add an exemption "
                "to this using hass.data for global storage not specific to a config entry.)",
            )
    return errors
