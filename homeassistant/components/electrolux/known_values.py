"""File containing mappings to all known values reported by entities by the Electrolux integration."""

from homeassistant.components import persistent_notification
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

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


def map_to_known_value(
    hass: HomeAssistant, platform: str, entity_name: str, value: str
) -> str:
    """Return the provided value if it is a known value, otherwise map it to unknown and create a notification for the user to open a PR."""
    if not is_known_value(platform, entity_name, value):
        persistent_notification.async_create(
            hass,
            title="Unknown value encountered",
            message=f'An unknown value {value} was reported for an entity for the Electrolux integration. Please open a PR for the integration, and include the following information: platform="{platform}", entity name="{entity_name}", reported value="{value}"',
        )
        return UNKNOWN
    return value
