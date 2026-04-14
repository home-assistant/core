"""File containing mappings to all known values reported by entities by the Electrolux integration."""

import logging

from homeassistant.const import Platform

_LOGGER: logging.Logger = logging.getLogger(__name__)

# embedded dictionary where the keys (from outer to inner order) are:
# platform, entity_name, value
KNOWN_VALUES: dict[str, dict[str, set[str]]] = {
    Platform.SENSOR: {
        "appliance_state": {
            "alarm",
            "delayed_start",
            "end_of_cycle",
            "idle",
            "off",
            "paused",
            "ready_to_start",
            "running",
        },
        "door_state": {
            "closed",
            "open",
        },
        "food_probe_state": {
            "inserted",
            "not_inserted",
        },
        "remote_control": {
            "disabled",
            "enabled",
            "not_safety_relevant_enabled",
            "temporary_locked",
        },
    }
}
UNKNOWN = "unknown"


def is_known_value(platform: str, entity_name: str, value: str) -> bool:
    """Check if provided value is supported or not."""
    return value in KNOWN_VALUES.get(platform, {}).get(entity_name, {})


def map_to_known_value(platform: str, entity_name: str, value: str) -> str:
    """Return provided value if it is known, otherwise log warn message and return 'unknown'."""
    if not is_known_value(platform, entity_name, value):
        _LOGGER.warning(
            "An unknown value %s was reported for an entity for the Electrolux integration. "
            "Please open a PR for the integration, and include the following information: "
            'platform="%s", entity name="%s", reported value="%s"',
            value,
            platform,
            entity_name,
            value,
        )
        return UNKNOWN
    return value
