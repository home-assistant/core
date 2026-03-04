"""Validate .core_files.yaml base_platforms alignment with entity platforms."""

import re

from homeassistant.util.yaml import load_yaml_dict

from .model import Config, Integration

# Non-entity-platform components that belong in base_platforms
EXTRA_BASE_PLATFORMS = {"diagnostics"}

_COMPONENT_RE = re.compile(r"homeassistant/components/([^/]+)/\*\*")


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
        if integration.manifest.get("integration_type") == "entity"
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
