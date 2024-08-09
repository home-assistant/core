"""Generate location file."""

from __future__ import annotations

from collections import defaultdict

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate location data."""
    region_domain_dict = defaultdict(list)

    for domain in sorted(integrations):
        integration = integrations[domain]
        regions = integration.manifest.get("locations", [])

        if not regions:
            continue

        for region in regions:
            region_domain_dict[region].append(domain)
    return format_python_namespace(
        {
            "LOCATIONS": region_domain_dict,
        }
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate locations file."""
    location_path = config.root / "homeassistant/generated/locations.py"
    config.cache["locations"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(location_path)) as fp:
        current = fp.read()
        if current != content:
            config.add_error(
                "locations",
                "File locations.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )
        return


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate locations file."""
    location_path = config.root / "homeassistant/generated/locations.py"
    with open(str(location_path), "w") as fp:
        fp.write(f"{config.cache['locations']}")
