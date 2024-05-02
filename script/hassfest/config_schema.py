"""Validate integrations which can be setup from YAML have config schemas."""

from __future__ import annotations

import ast

from homeassistant.core import DOMAIN as HA_DOMAIN

from .model import Config, Integration

CONFIG_SCHEMA_IGNORE = {
    # Configuration under the homeassistant key is a special case, it's handled by
    # conf_util.async_process_ha_core_config already during bootstrapping, not by
    # a schema in the homeassistant integration.
    HA_DOMAIN,
}


def _has_assignment(module: ast.Module, name: str) -> bool:
    """Test if the module assigns to a name."""
    for item in module.body:
        if type(item) not in (ast.Assign, ast.AnnAssign, ast.AugAssign):
            continue
        if type(item) == ast.Assign:
            for target in item.targets:
                if getattr(target, "id", None) == name:
                    return True
            continue
        if item.target.id == name:
            return True
    return False


def _has_function(
    module: ast.Module, _type: ast.AsyncFunctionDef | ast.FunctionDef, name: str
) -> bool:
    """Test if the module defines a function."""
    return any(type(item) == _type and item.name == name for item in module.body)


def _has_import(module: ast.Module, name: str) -> bool:
    """Test if the module imports to a name."""
    for item in module.body:
        if type(item) not in (ast.Import, ast.ImportFrom):
            continue
        for alias in item.names:
            if alias.asname == name or (alias.asname is None and alias.name == name):
                return True
    return False


def _validate_integration(config: Config, integration: Integration) -> None:
    """Validate integration has has a configuration schema."""
    if integration.domain in CONFIG_SCHEMA_IGNORE:
        return

    init_file = integration.path / "__init__.py"

    if not init_file.is_file():
        # Virtual integrations don't have any implementation
        return

    init = ast.parse(init_file.read_text())

    # No YAML Support
    if not _has_function(
        init, ast.AsyncFunctionDef, "async_setup"
    ) and not _has_function(init, ast.FunctionDef, "setup"):
        return

    # No schema
    if (
        _has_assignment(init, "CONFIG_SCHEMA")
        or _has_assignment(init, "PLATFORM_SCHEMA")
        or _has_assignment(init, "PLATFORM_SCHEMA_BASE")
        or _has_import(init, "CONFIG_SCHEMA")
        or _has_import(init, "PLATFORM_SCHEMA")
        or _has_import(init, "PLATFORM_SCHEMA_BASE")
    ):
        return

    config_file = integration.path / "config.py"
    if config_file.is_file():
        config_module = ast.parse(config_file.read_text())
        if _has_function(config_module, ast.AsyncFunctionDef, "async_validate_config"):
            return

    if config.specific_integrations:
        notice_method = integration.add_warning
    else:
        notice_method = integration.add_error

    notice_method(
        "config_schema",
        "Integrations which implement 'async_setup' or 'setup' must define either "
        "'CONFIG_SCHEMA', 'PLATFORM_SCHEMA' or 'PLATFORM_SCHEMA_BASE'. If the "
        "integration has no configuration parameters, can only be set up from platforms"
        " or can only be set up from config entries, one of the helpers "
        "cv.empty_config_schema, cv.platform_only_config_schema or "
        "cv.config_entry_only_config_schema can be used.",
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integrations have configuration schemas."""
    for domain in sorted(integrations):
        integration = integrations[domain]
        _validate_integration(config, integration)
