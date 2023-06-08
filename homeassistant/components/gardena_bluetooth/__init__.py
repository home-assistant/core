"""The Gardena Bluetooth integration."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from bleak.exc import BleakError
from gardena_bluetooth import (
    get_all_characteristics_uuid,
    read_char,
    update_timestamp,
)
from gardena_bluetooth.const import DeviceConfiguration, DeviceInformation
from gardena_bluetooth.exceptions import CharacteristicNoAccess

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import Coordinator, DeviceUnavailable

PLATFORMS: list[Platform] = [Platform.SWITCH]
LOGGER = logging.getLogger(__name__)
TIMEOUT = 20.0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    address = entry.data[CONF_ADDRESS]
    device_registry = dr.async_get(hass)
    coordinator = Coordinator(hass, LOGGER, address)

    try:
        async with coordinator.client() as client:
            sw_version = await read_char(client, DeviceInformation.firmware_version)
            manufacturer = await read_char(client, DeviceInformation.manufacturer_name)

            model = await read_char(client, DeviceInformation.model_number)
            try:
                name = await read_char(client, DeviceConfiguration.custom_device_name)
            except CharacteristicNoAccess:
                name = None

            await update_timestamp(
                client, datetime.now(dt_util.get_time_zone(hass.config.time_zone))
            )

            coordinator.characteristics = await get_all_characteristics_uuid(client)
            LOGGER.debug("Characteristics: %s", coordinator.characteristics)

            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, address)},
                name=name or entry.title,
                sw_version=sw_version,
                manufacturer=manufacturer,
                model=model,
            )
    except asyncio.TimeoutError as exception:
        raise ConfigEntryNotReady("Unable to connect to device") from exception
    except DeviceUnavailable as exception:
        raise ConfigEntryNotReady(
            f"Could not find Gardena Device with address {address}"
        ) from exception
    except BleakError as exception:
        raise ConfigEntryNotReady(
            f"Connection to Gardena Device with address {address} failed {exception}"
        ) from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok
