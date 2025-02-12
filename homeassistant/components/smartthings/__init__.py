"""Support for SmartThings Cloud."""

from __future__ import annotations

import asyncio
import logging

from pysmartthings import SmartThings

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_LOCATION_ID
from .coordinator import (
    SmartThingsConfigEntry,
    SmartThingsData,
    SmartThingsDeviceCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: SmartThingsConfigEntry) -> bool:
    """Initialize config entry which represents an installed SmartApp."""
    client = SmartThings(
        entry.data[CONF_ACCESS_TOKEN], session=async_get_clientsession(hass)
    )

    try:
        devices = await client.get_devices(location_ids=[entry.data[CONF_LOCATION_ID]])
    except Exception:
        _LOGGER.exception("Failed to fetch devices")
        entry.runtime_data = SmartThingsData(devices=[], client=client, scenes={})
        return True

    coordinators = [
        SmartThingsDeviceCoordinator(hass, entry, client, device) for device in devices
    ]

    await asyncio.gather(*[coordinator.async_refresh() for coordinator in coordinators])

    scenes = {
        scene.scene_id: scene
        for scene in await client.get_scenes(location_id=entry.data[CONF_LOCATION_ID])
    }

    entry.runtime_data = SmartThingsData(
        devices=[
            coordinator for coordinator in coordinators if coordinator.data is not None
        ],
        client=client,
        scenes=scenes,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
