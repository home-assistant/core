"""Generate the locations file."""

from collections import defaultdict

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration], config: Config) -> str:
    """Validate and generate location data."""
    country_domains: defaultdict[str, list[str]] = defaultdict(list)

    for domain in sorted(integrations):
        for country in integrations[domain].manifest.get("locations", []):
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

    if location_path.read_text() != content:
        config.add_error(
            "locations",
            "File locations.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate locations file."""
    location_path = config.root / "homeassistant/generated/locations.py"
    location_path.write_text(f"{config.cache['locations']}")
