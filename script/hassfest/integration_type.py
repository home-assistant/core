"""Validate integration type is set for config flow integrations."""

from __future__ import annotations

from .model import Config, Integration

# Integrations with config_flow that are missing integration_type.
# These need to be fixed; do not add new entries to this list.
MISSING_INTEGRATION_TYPE = {
    "abode",
    "acmeda",
    "adax",
    "awair",
    "bluetooth",
    "bthome",
    "chacon_dio",
    "color_extractor",
    "crownstone",
    "deako",
    "dialogflow",
    "dynalite",
    "elmax",
    "emulated_roku",
    "ezviz",
    "file",
    "filesize",
    "fluss",
    "flux_led",
    "folder_watcher",
    "forked_daapd",
    "geniushub",
    "gentex_homelink",
    "geofency",
    "govee_light_local",
    "gpsd",
    "gpslogger",
    "gree",
    "holiday",
    "homekit",
    "html5",
    "ifttt",
    "influxdb",
    "ios",
    "jewish_calendar",
    "local_calendar",
    "local_file",
    "local_ip",
    "local_todo",
    "locative",
    "mcp",
    "media_extractor",
    "mill",
    "mjpeg",
    "modern_forms",
    "ness_alarm",
    "nmap_tracker",
    "otp",
    "orvibo",
    "profiler",
    "proximity",
    "rhasspy",
    "risco",
    "rpi_power",
    "scrape",
    "shopping_list",
    "sql",
    "sunweg",
    "systemmonitor",
    "tasmota",
    "traccar",
    "traccar_server",
    "upb",
    "version",
    "volvooncall",
    "wemo",
    "zodiac",
}


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate that all config flow integrations declare an integration type."""
    for integration in integrations.values():
        if not integration.config_flow or not integration.core:
            continue

        if "integration_type" in integration.manifest:
            if integration.domain in MISSING_INTEGRATION_TYPE:
                integration.add_error(
                    "integration_type",
                    "Integration has an `integration_type` in the manifest but is still listed in MISSING_INTEGRATION_TYPE",
                )
            continue

        if integration.domain in MISSING_INTEGRATION_TYPE:
            continue

        integration.add_error(
            "integration_type",
            "Integration has a config flow but is missing an `integration_type` in the manifest",
        )
