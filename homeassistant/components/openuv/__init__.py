"""Support for UV data from openuv.io."""

import asyncio
from typing import Any

from pyopenuv.client import Client

from homeassistant.const import (
    CONF_API_KEY,
    CONF_BINARY_SENSORS,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_SENSORS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_FROM_WINDOW,
    CONF_TO_WINDOW,
    DATA_PROTECTION_WINDOW,
    DATA_UV,
    DEFAULT_FROM_WINDOW,
    DEFAULT_TO_WINDOW,
    LOGGER,
)
from .coordinator import (
    OpenUvConfigEntry,
    OpenUvCoordinator,
    OpenUvProtectionWindowCoordinator,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpenUvConfigEntry) -> None:
    """Set up OpenUV as config entry."""
    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(
        entry.data[CONF_API_KEY],
        entry.data[CONF_LOCATION][CONF_LATITUDE],
        entry.data[CONF_LOCATION][CONF_LONGITUDE],
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
        coordinator_name: coordinator_cls(
            hass,
            entry=entry,
            name=coordinator_name,
            latitude=client.latitude,
            longitude=client.longitude,
            update_method=update_method,
        )
        for coordinator_cls, coordinator_name, update_method in (
            (OpenUvCoordinator, DATA_UV, client.uv_index),
            (
                OpenUvProtectionWindowCoordinator,
                DATA_PROTECTION_WINDOW,
                async_update_protection_data,
            ),
        )
    }

    init_tasks = [
        coordinator.async_config_entry_first_refresh()
        for coordinator in coordinators.values()
    ]
    await asyncio.gather(*init_tasks)

    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: OpenUvConfigEntry) -> None:
    """Unload an OpenUV config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: OpenUvConfigEntry) -> None:
    """Migrate the config entry upon new versions."""
    LOGGER.debug("Migrating from version %s", entry.version)

    # 1 -> 2: Remove unused condition data:
    if entry.version < 2:
        data = dict(entry.data)
        data.pop(CONF_BINARY_SENSORS, None)
        data.pop(CONF_SENSORS, None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        LOGGER.debug("Migration to version %s successful", 2)
    if entry.version < 3:
        data = dict(entry.data)
        long = data.pop(CONF_LONGITUDE, hass.config.longitude)
        lat = data.pop(CONF_LATITUDE, hass.config.latitude)
        data[CONF_LOCATION] = {CONF_LATITUDE: lat, CONF_LONGITUDE: long}
        hass.config_entries.async_update_entry(entry, data=data, version=3)
        LOGGER.debug("Migration to version %s successful", 3)
