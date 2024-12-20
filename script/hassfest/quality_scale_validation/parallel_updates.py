"""Enforce that the integration sets PARALLEL_UPDATES constant.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/parallel-updates
"""

import ast

from homeassistant.const import Platform
from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration


def _has_parallel_updates_defined(module: ast.Module) -> bool:
    """Test if the module defines `PARALLEL_UPDATES` constant."""
    return any(
        type(item) is ast.Assign and item.targets[0].id == "PARALLEL_UPDATES"
        for item in module.body
    )


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that the integration sets PARALLEL_UPDATES constant."""

    errors = []
    for platform in Platform:
        module_file = integration.path / f"{platform}.py"
        if not module_file.exists():
            continue
        module = ast_parse_module(module_file)

        if not _has_parallel_updates_defined(module):
            errors.append(
                f"Integration does not set `PARALLEL_UPDATES` in {module_file}"
            )

    return errors
