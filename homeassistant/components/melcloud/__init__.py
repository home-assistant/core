"""The MELCloud Climate integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from aiohttp import ClientConnectionError, ClientResponseError
from pymelcloud import get_devices

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .coordinator import MelCloudConfigEntry, MelCloudDeviceUpdateCoordinator

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.WATER_HEATER]


async def async_setup_entry(hass: HomeAssistant, entry: MelCloudConfigEntry) -> bool:
    """Establish connection with MELCloud."""
    token = entry.data[CONF_TOKEN]
    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(10):
            all_devices = await get_devices(
                token,
                session,
                conf_update_interval=timedelta(minutes=30),
                device_set_debounce=timedelta(seconds=2),
            )
    except ClientResponseError as ex:
        if ex.status in (401, 403):
            raise ConfigEntryAuthFailed from ex
        if ex.status == 429:
            raise UpdateFailed(
                "MELCloud rate limit exceeded. Your account may be temporarily blocked"
            ) from ex
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex
    except (TimeoutError, ClientConnectionError) as ex:
        raise UpdateFailed(f"Error communicating with MELCloud: {ex}") from ex

    # Create per-device coordinators
    coordinators: dict[str, list[MelCloudDeviceUpdateCoordinator]] = {}
    device_registry = dr.async_get(hass)
    for device_type, devices in all_devices.items():
        coordinators[device_type] = []
        for device in devices:
            coordinator = MelCloudDeviceUpdateCoordinator(hass, device, entry)
            # Perform initial refresh for this device
            await coordinator.async_config_entry_first_refresh()
            coordinators[device_type].append(coordinator)
            # Register parent device now so zone entities can reference it via via_device
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                **coordinator.mel_device.device_info,
            )

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
