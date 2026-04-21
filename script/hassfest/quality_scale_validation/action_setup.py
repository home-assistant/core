"""Enforce that the integration service actions are registered in async_setup.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/action-setup/
"""

import ast

from script.hassfest import ast_parse_module
from script.hassfest.manifest import Platform
from script.hassfest.model import Config, Integration


def _get_setup_entry_function(module: ast.Module) -> ast.AsyncFunctionDef | None:
    """Get async_setup_entry function."""
    for item in module.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == "async_setup_entry":
            return item
    return None


def _calls_service_registration(
    async_setup_entry_function: ast.AsyncFunctionDef,
) -> bool:
    """Check if there are calls to service registration."""
    for node in ast.walk(async_setup_entry_function):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue

        if node.func.attr == "async_register_entity_service":
            return True

        if (
            isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
            and node.func.value.value.id == "hass"
            and node.func.value.attr == "services"
            and node.func.attr in {"async_register", "register"}
        ):
            return True

    return False


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate that service actions are registered in async_setup."""

    errors = []

    module_file = integration.path / "__init__.py"
    module = ast_parse_module(module_file)
    if (
        async_setup_entry := _get_setup_entry_function(module)
    ) and _calls_service_registration(async_setup_entry):
        errors.append(
            f"Integration registers services in {module_file} (async_setup_entry)"
        )

    for platform in Platform:
        module_file = integration.path / f"{platform}.py"
        if not module_file.exists():
            continue
        module = ast_parse_module(module_file)

        if (
            async_setup_entry := _get_setup_entry_function(module)
        ) and _calls_service_registration(async_setup_entry):
            errors.append(
                f"Integration registers services in {module_file} (async_setup_entry)"
            )

    return errors
