"""Button platform for ISS integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ISS button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    tle_coordinator = data["tle_coordinator"]

    async_add_entities(
        [
            IssRefreshTleButton(tle_coordinator, entry),
        ]
    )


class IssRefreshTleButton(ButtonEntity):
    """Button to clear TLE cache and force refresh."""

    _attr_has_entity_name = True
    _attr_translation_key = "refresh_tle_cache"
    _attr_icon = "mdi:refresh"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, tle_coordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        self._tle_coordinator = tle_coordinator
        self._attr_unique_id = f"{entry.entry_id}_refresh_tle"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def async_press(self) -> None:
        """Clear TLE cache and force refresh."""
        self._logger.info("Clearing TLE cache and forcing refresh")
        # Clear the cache
        await self._tle_coordinator.async_clear_cache()
        # Force immediate refresh
        await self._tle_coordinator.async_request_refresh()
