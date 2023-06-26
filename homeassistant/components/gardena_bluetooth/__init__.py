"""The Gardena Bluetooth integration."""
from __future__ import annotations

import asyncio
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from gardena_bluetooth import (
    get_all_characteristics_uuid,
    read_char,
    update_timestamp,
)
from gardena_bluetooth.client import CachedClient
from gardena_bluetooth.const import DeviceConfiguration, DeviceInformation

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import Coordinator, DeviceUnavailable

PLATFORMS: list[Platform] = [Platform.SWITCH]
LOGGER = logging.getLogger(__name__)
TIMEOUT = 20.0
DISCONNECT_DELAY = 5


async def async_get_device_info(client: BleakClient, entry_title: str):
    """Retrieve a device information structure from a device."""
    sw_version = await read_char(client, DeviceInformation.firmware_version, None)
    manufacturer = await read_char(client, DeviceInformation.manufacturer_name, None)
    model = await read_char(client, DeviceInformation.model_number, None)
    name = await read_char(client, DeviceConfiguration.custom_device_name, entry_title)

    return DeviceInfo(
        identifiers={(DOMAIN, client.address)},
        name=name,
        sw_version=sw_version,
        manufacturer=manufacturer,
        model=model,
    )


def get_cached_client(hass: HomeAssistant, address: str) -> CachedClient:
    """Set up a cached client that keeps connection after last use."""

    def _device_lookup() -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        if not device:
            raise DeviceUnavailable("Unable to find device")
        return device

    return CachedClient(DISCONNECT_DELAY, _device_lookup)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    address = entry.data[CONF_ADDRESS]
    cached_client = get_cached_client(hass, address)
    try:
        async with cached_client() as client:
            device = await async_get_device_info(client, entry.title)
            uuids = await get_all_characteristics_uuid(client)
            await update_timestamp(client, dt_util.now())
    except (asyncio.TimeoutError, DeviceUnavailable, BleakError) as exception:
        await cached_client.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to device {address} due to {exception}"
        ) from exception

    coordinator = Coordinator(hass, LOGGER, cached_client, uuids, device, address)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()

    return unload_ok
