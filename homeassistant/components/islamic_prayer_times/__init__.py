"""The islamic_prayer_times component."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .coordinator import (
    IslamicPrayerDataUpdateCoordinator,
    IslamicPrayerTimesConfigEntry,
)

PLATFORMS = [Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: IslamicPrayerTimesConfigEntry
) -> bool:
    """Set up the Islamic Prayer Component."""

    @callback
    def update_unique_id(
        entity_entry: er.RegistryEntry,
    ) -> dict[str, str] | None:
        """Update unique ID of entity entry."""
        if not entity_entry.unique_id.startswith(f"{config_entry.entry_id}-"):
            new_unique_id = f"{config_entry.entry_id}-{entity_entry.unique_id}"
            return {"new_unique_id": new_unique_id}
        return None

    await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

    coordinator = IslamicPrayerDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_options_updated)
    )
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: IslamicPrayerTimesConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False
    if config_entry.version == 1:
        new = {**config_entry.data}
        if config_entry.minor_version < 2:
            lat = hass.config.latitude
            lon = hass.config.longitude
            new = {
                CONF_LATITUDE: lat,
                CONF_LONGITUDE: lon,
            }
            unique_id = f"{lat}-{lon}"
        hass.config_entries.async_update_entry(
            config_entry, data=new, unique_id=unique_id, version=1, minor_version=2
        )

    _LOGGER.debug("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: IslamicPrayerTimesConfigEntry
) -> bool:
    """Unload Islamic Prayer entry from config_entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        coordinator = config_entry.runtime_data
        if coordinator.event_unsub:
            coordinator.event_unsub()
    return unload_ok


async def async_options_updated(
    hass: HomeAssistant, entry: IslamicPrayerTimesConfigEntry
) -> None:
    """Triggered by config entry options updates."""
    coordinator = entry.runtime_data
    if coordinator.event_unsub:
        coordinator.event_unsub()
    await coordinator.async_request_refresh()
