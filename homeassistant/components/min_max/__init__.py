"""The min_max component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Min/Max from a config entry."""
    async_create_issue(
        hass,
        DOMAIN,
        "migrate_to_group_sensor",
        is_fixable=True,
        is_persistent=False,
        severity=IssueSeverity.WARNING,
        translation_key="migrate_to_group_sensor",
        translation_placeholders={"title": entry.title},
        data={"entry_id": entry.entry_id},
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
