"""The min_max component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DEPRECATION_BREAKS_IN_HA_VERSION, DOMAIN

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]

__all__ = [
    "DOMAIN",
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Min/Max from a config entry."""
    async_create_issue(
        hass,
        DOMAIN,
        f"migrate_to_group_sensor-{entry.entry_id}",
        breaks_in_ha_version=DEPRECATION_BREAKS_IN_HA_VERSION,
        is_fixable=True,
        is_persistent=False,
        severity=IssueSeverity.WARNING,
        translation_key="migrate_to_group_sensor",
        data={"entry_id": entry.entry_id},
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    async_delete_issue(hass, DOMAIN, f"migrate_to_group_sensor-{entry.entry_id}")
