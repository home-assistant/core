"""Support for UV data from openuv.io."""
from __future__ import annotations

import asyncio
from typing import Any

from pyopenuv import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    DOMAIN,
    LOGGER,
)
from .coordinator import OpenUvCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OpenUV as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(
        entry.data[CONF_API_KEY],
        entry.data.get(CONF_LATITUDE, hass.config.latitude),
        entry.data.get(CONF_LONGITUDE, hass.config.longitude),
        altitude=entry.data.get(CONF_ELEVATION, hass.config.elevation),
        session=websession,
        check_status_before_request=True,
    )

    async def async_update_protection_data() -> dict[str, Any]:
        """Update binary sensor (protection window) data."""
        low = entry.options.get(CONF_FROM_WINDOW, DEFAULT_FROM_WINDOW)
        high = entry.options.get(CONF_TO_WINDOW, DEFAULT_TO_WINDOW)
        return await client.uv_protection_window(low=low, high=high)

    coordinators: dict[str, OpenUvCoordinator] = {
        coordinator_name: OpenUvCoordinator(
            hass,
            entry=entry,
            name=coordinator_name,
            latitude=client.latitude,
            longitude=client.longitude,
            update_method=update_method,
        )
        for coordinator_name, update_method in (
            (DATA_UV, client.uv_index),
            (DATA_PROTECTION_WINDOW, async_update_protection_data),
        )
    }

    init_tasks = [
        coordinator.async_config_entry_first_refresh()
        for coordinator in coordinators.values()
    ]
    await asyncio.gather(*init_tasks)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an OpenUV config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the config entry upon new versions."""
    version = entry.version
    data = {**entry.data}

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Remove unused condition data:
    if version == 1:
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        version = entry.version = 2
        hass.config_entries.async_update_entry(entry, data=data)
        LOGGER.debug("Migration to version %s successful", version)

    return True


class OpenUvEntity(CoordinatorEntity):
    """Define a generic OpenUV entity."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: OpenUvCoordinator, description: EntityDescription
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self._attr_extra_state_attributes = {}
        self._attr_unique_id = (
            f"{coordinator.latitude}_{coordinator.longitude}_{description.key}"
        )
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.latitude}_{coordinator.longitude}")},
            name="OpenUV",
            entry_type=DeviceEntryType.SERVICE,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Respond to a DataUpdateCoordinator update."""
        self._update_from_latest_data()
        self.async_write_ha_state()

    @callback
    def _update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        self._update_from_latest_data()
