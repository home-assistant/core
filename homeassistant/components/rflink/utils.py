"""RFLink integration utils."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, EVENT_KEY_COMMAND, EVENT_KEY_SENSOR


def brightness_to_rflink(brightness: int) -> int:
    """Convert 0-255 brightness to RFLink dim level (0-15)."""
    return int(brightness / 17)


def rflink_to_brightness(dim_level: int) -> int:
    """Convert RFLink dim level (0-15) to 0-255 brightness."""
    return int(dim_level * 17)


def identify_event_type(event):
    """Look at event to determine type of device.

    Async friendly.
    """
    if EVENT_KEY_COMMAND in event:
        return EVENT_KEY_COMMAND
    if EVENT_KEY_SENSOR in event:
        return EVENT_KEY_SENSOR
    return "unknown"


def create_issue_yaml_migration(hass: HomeAssistant, platform: str):
    """Create a YAML migration repair."""
    async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id=f"{platform}_yaml_migration",
        breaks_in_ha_version="2026.10.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        learn_more_url="https://www.home-assistant.io/integrations/rflink/#migrating-from-legacy-configuration-format",
        severity=IssueSeverity.WARNING,
        translation_key="yaml_migration",
        translation_placeholders={
            "platform": platform,
        },
    )
