"""Write integration constants."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate integrations file."""

    if config.specific_integrations:
        return

    int_type = "entity"

    domains = [
        integration.domain
        for integration in integrations.values()
        if integration.manifest.get("integration_type") == int_type
        # Tag is type "entity" but has no entity platform
        and integration.domain != "tag"
    ]

    code = [
        "from enum import StrEnum",
        "class EntityPlatforms(StrEnum):",
        f'    """Available {int_type} platforms."""',
    ]
    code.extend([f'    {domain.upper()} = "{domain}"' for domain in sorted(domains)])

    config.cache[f"integrations_{int_type}"] = format_python(
        "\n".join(code), generator="script.hassfest"
    )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate integration file."""
    int_type = "entity"
    filename = "entity_platforms"
    platform_path = config.root / f"homeassistant/generated/{filename}.py"
    platform_path.write_text(config.cache[f"integrations_{int_type}"])
