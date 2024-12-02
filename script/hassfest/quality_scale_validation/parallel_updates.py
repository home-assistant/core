"""Enforce that the integration set Parallel updates.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates
"""

import ast

from homeassistant.const import Platform
from script.hassfest.model import Integration


def _has_parallel_updates_defined(module: ast.Module) -> bool:
    """Test if the module defines `PARALLEL_UPDATES` constant."""
    return any(
        type(item) is ast.Assign and item.targets[0].id == "PARALLEL_UPDATES"
        for item in module.body
    )


def validate(integration: Integration) -> list[str] | None:
    """Validate that the integration has a reauthentication flow."""

    errors = []
    for platform in Platform:
        module_file = integration.path / f"{platform}.py"
        if not module_file.exists():
            continue
        module = ast.parse(module_file.read_text())

        if not _has_parallel_updates_defined(module):
            errors.append(
                "Integration does not support a reauthentication flow "
                f"(is missing `PARALLEL_UPDATES` in {module_file})"
            )

    return errors
