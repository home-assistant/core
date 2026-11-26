"""Generate the locations file."""

from collections import defaultdict

from hassfest.model import Config, Integration
from hassfest.serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration], config: Config) -> str:
    """Validate and generate location data."""
    country_domains: defaultdict[str, list[str]] = defaultdict(list)

    for domain in sorted(integrations):
        integration = integrations[domain]
        locations = integration.manifest.get("locations", [])
        # This plugin runs before manifest validation, so the value is unchecked.
        if not isinstance(locations, list) or not all(
            isinstance(country, str) for country in locations
        ):
            integration.add_error("locations", "locations must be a list of strings")
            continue
        for country in locations:
            country_domains[country].append(domain)

    return format_python_namespace(
        {"LOCATIONS": dict(sorted(country_domains.items()))},
        annotations={"LOCATIONS": "Final[dict[str, list[str]]]"},
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate locations file."""
    location_path = config.root / "homeassistant/generated/locations.py"
    config.cache["locations"] = content = generate_and_validate(integrations, config)

    if config.specific_integrations:
        return

    if not location_path.exists() or location_path.read_text() != content:
        config.add_error(
            "locations",
            "File locations.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate locations file."""
    location_path = config.root / "homeassistant/generated/locations.py"
    location_path.write_text(f"{config.cache['locations']}")
