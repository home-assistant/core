"""Validate .core_files.yaml and the core integrations it lists."""

import ast
from pathlib import Path
import re

from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration, IntegrationType

# Non-entity-platform components that belong in base_platforms
EXTRA_BASE_PLATFORMS = {"diagnostics"}

# Core integrations that do not define __all__ yet.
# These need to be fixed; do not add new entries to this list.
MISSING_ALL = {
    "configurator",  # Deprecated, to be removed in 2027.10
}

_COMPONENT_RE = re.compile(r"homeassistant/components/([^/]+)/\*\*")


def get_core_integrations(root: Path) -> set[str]:
    """Return the integrations listed in .core_files.yaml."""
    core_files = load_yaml_dict(str(root / ".core_files.yaml"))
    return {
        match.group(1)
        for entry in (*core_files["base_platforms"], *core_files.get("components", []))
        if (match := _COMPONENT_RE.match(entry))
    }


def _defines_all(init_file: Path) -> bool:
    """Return True if the module assigns __all__ at module level."""
    for node in ast.parse(init_file.read_text(), str(init_file)).body:
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue
        if any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in targets
        ):
            return True
    return False


def _validate_public_names(
    integrations: dict[str, Integration], config: Config, core_domains: set[str]
) -> None:
    """Validate that core integrations define __all__ in their package root."""
    for domain in sorted(core_domains):
        if (integration := integrations.get(domain)) is None:
            continue
        init_file = integration.path / "__init__.py"
        if not init_file.is_file():
            continue
        defines_all = _defines_all(init_file)
        if domain in MISSING_ALL:
            if defines_all:
                config.add_error(
                    "core_files",
                    f"Core integration '{domain}' defines `__all__` "
                    "but is still listed in MISSING_ALL",
                )
            continue
        if not defines_all:
            config.add_error(
                "core_files",
                f"Core integration '{domain}' must define `__all__` "
                "in its `__init__.py`",
            )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate that base_platforms in .core_files.yaml matches entity platforms."""
    if config.specific_integrations:
        return

    core_files_path = config.root / ".core_files.yaml"
    core_files = load_yaml_dict(str(core_files_path))

    base_platform_entries = {
        match.group(1)
        for entry in core_files["base_platforms"]
        if (match := _COMPONENT_RE.match(entry))
    }

    entity_platforms = {
        integration.domain
        for integration in integrations.values()
        if integration.integration_type == IntegrationType.ENTITY
        and integration.domain != "tag"
    }

    expected = entity_platforms | EXTRA_BASE_PLATFORMS

    for domain in sorted(expected - base_platform_entries):
        config.add_error(
            "core_files",
            f"Entity platform '{domain}' is missing from "
            "base_platforms in .core_files.yaml",
        )

    for domain in sorted(base_platform_entries - expected):
        config.add_error(
            "core_files",
            f"'{domain}' in base_platforms in .core_files.yaml "
            "is not an entity platform or in EXTRA_BASE_PLATFORMS",
        )

    component_entries = {
        match.group(1)
        for entry in core_files.get("components", [])
        if (match := _COMPONENT_RE.match(entry))
    }
    _validate_public_names(
        integrations, config, base_platform_entries | component_entries
    )
