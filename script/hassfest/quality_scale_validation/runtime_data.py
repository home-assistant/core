"""Enforce that the integration uses ConfigEntry.runtime_data to store runtime data.

https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/runtime-data
"""

import ast
import re

from homeassistant.const import Platform
from script.hassfest import ast_parse_module
from script.hassfest.model import Config, Integration

_ANNOTATION_MATCH = re.compile(r"^[A-Za-z]+ConfigEntry$")
_FUNCTIONS: dict[str, dict[str, int]] = {
    "__init__": {  # based on ComponentProtocol
        "async_migrate_entry": 2,
        "async_remove_config_entry_device": 2,
        "async_remove_entry": 2,
        "async_setup_entry": 2,
        "async_unload_entry": 2,
    },
    "diagnostics": {  # based on DiagnosticsProtocol
        "async_get_config_entry_diagnostics": 2,
        "async_get_device_diagnostics": 2,
    },
}
for platform in Platform:  # based on EntityPlatformModule
    _FUNCTIONS[platform.value] = {
        "async_setup_entry": 2,
    }


def _sets_runtime_data(
    async_setup_entry_function: ast.AsyncFunctionDef, config_entry_argument: ast.arg
) -> bool:
    """Check that `entry.runtime` gets set within `async_setup_entry`."""
    for node in ast.walk(async_setup_entry_function):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == config_entry_argument.arg
            and node.attr == "runtime_data"
            and isinstance(node.ctx, ast.Store)
        ):
            return True
    return False


def _get_async_function(module: ast.Module, name: str) -> ast.AsyncFunctionDef | None:
    """Get async function."""
    for item in module.body:
        if isinstance(item, ast.AsyncFunctionDef) and item.name == name:
            return item
    return None


def _check_function_annotation(
    function: ast.AsyncFunctionDef, position: int
) -> str | None:
    """Ensure function uses CustomConfigEntry type annotation."""
    if len(function.args.args) < position:
        return f"{function.name} has incorrect signature"
    argument = function.args.args[position - 1]
    if not (
        (annotation := argument.annotation)
        and isinstance(annotation, ast.Name)
        and _ANNOTATION_MATCH.match(annotation.id)
    ):
        return f"([+ strict-typing]) {function.name} does not use typed ConfigEntry"
    return None


def _check_typed_config_entry(integration: Integration) -> list[str]:
    """Ensure integration uses CustomConfigEntry type annotation."""
    errors: list[str] = []
    # Check body level function annotations
    for file, functions in _FUNCTIONS.items():
        module_file = integration.path / f"{file}.py"
        if not module_file.exists():
            continue
        module = ast_parse_module(module_file)
        for function, position in functions.items():
            if not (async_function := _get_async_function(module, function)):
                continue
            if error := _check_function_annotation(async_function, position):
                errors.append(f"{error} in {module_file}")

    # Check config_flow annotations
    config_flow_file = integration.path / "config_flow.py"
    config_flow = ast_parse_module(config_flow_file)
    for node in config_flow.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if any(
            isinstance(async_function, ast.FunctionDef)
            and async_function.name == "async_get_options_flow"
            and (error := _check_function_annotation(async_function, 1))
            for async_function in node.body
        ):
            errors.append(f"{error} in {config_flow_file}")

    return errors


def validate(
    config: Config, integration: Integration, *, rules_done: set[str]
) -> list[str] | None:
    """Validate correct use of ConfigEntry.runtime_data."""
    init_file = integration.path / "__init__.py"
    init = ast_parse_module(init_file)

    # Should not happen, but better to be safe
    if not (async_setup_entry := _get_async_function(init, "async_setup_entry")):
        return [f"Could not find `async_setup_entry` in {init_file}"]
    if len(async_setup_entry.args.args) != 2:
        return [f"async_setup_entry has incorrect signature in {init_file}"]
    config_entry_argument = async_setup_entry.args.args[1]

    errors: list[str] = []
    if not _sets_runtime_data(async_setup_entry, config_entry_argument):
        errors.append(
            "Integration does not set entry.runtime_data in async_setup_entry"
            f"({init_file})"
        )

    # Extra checks, if strict-typing is marked as done
    if "strict-typing" in rules_done:
        errors.extend(_check_typed_config_entry(integration))

    return errors
