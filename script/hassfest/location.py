"""Validate location regions and generate the locations file."""

from collections import defaultdict
import json

from homeassistant.components.location.region import REGION_FILE_SUFFIX, load_region

from .model import Config, Integration
from .serializer import format_python_namespace

REGIONS_PATH = "homeassistant/components/location/regions"


def generate_and_validate(integrations: dict[str, Integration], config: Config) -> str:
    """Validate and generate location data."""
    region_paths = {
        path.stem: path
        for path in (config.root / REGIONS_PATH).glob(f"*{REGION_FILE_SUFFIX}")
    }
    region_domains: defaultdict[str, list[str]] = defaultdict(list)

    for domain in sorted(integrations):
        integration = integrations[domain]
        for region_id in integration.manifest.get("locations", []):
            if region_id not in region_paths:
                integration.add_error(
                    "location",
                    f"Unknown region {region_id}, add {REGIONS_PATH}/"
                    f"{region_id}{REGION_FILE_SUFFIX}",
                )
                continue
            region_domains[region_id].append(domain)

    for region_id, path in sorted(region_paths.items()):
        try:
            load_region(path)
        except (ValueError, json.JSONDecodeError) as err:
            config.add_error("location", f"Invalid region {region_id}: {err}")
        if not config.specific_integrations and region_id not in region_domains:
            config.add_error(
                "location", f"Region {region_id} is not used by any integration"
            )

    return format_python_namespace(
        {"LOCATIONS": dict(sorted(region_domains.items()))},
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
