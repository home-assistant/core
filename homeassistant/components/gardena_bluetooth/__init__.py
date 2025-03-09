"""The Gardena Bluetooth integration."""

from __future__ import annotations

import logging

from bleak.backends.device import BLEDevice
from gardena_bluetooth.client import CachedConnection, Client
from gardena_bluetooth.const import DeviceConfiguration, DeviceInformation
from gardena_bluetooth.exceptions import CommunicationFailure

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import (
    DeviceUnavailable,
    GardenaBluetoothConfigEntry,
    GardenaBluetoothCoordinator,
)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VALVE,
]
LOGGER = logging.getLogger(__name__)
TIMEOUT = 20.0
DISCONNECT_DELAY = 5


def get_connection(hass: HomeAssistant, address: str) -> CachedConnection:
    """Set up a cached client that keeps connection after last use."""

    def _device_lookup() -> BLEDevice:
        device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        if not device:
            raise DeviceUnavailable("Unable to find device")
        return device

    return CachedConnection(DISCONNECT_DELAY, _device_lookup)


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Set up Gardena Bluetooth from a config entry."""

    address = entry.data[CONF_ADDRESS]
    client = Client(get_connection(hass, address))
    try:
        sw_version = await client.read_char(DeviceInformation.firmware_version, None)
        manufacturer = await client.read_char(DeviceInformation.manufacturer_name, None)
        model = await client.read_char(DeviceInformation.model_number, None)
        name = await client.read_char(
            DeviceConfiguration.custom_device_name, entry.title
        )
        uuids = await client.get_all_characteristics_uuid()
        await client.update_timestamp(dt_util.now())
    except (TimeoutError, CommunicationFailure, DeviceUnavailable) as exception:
        await client.disconnect()
        raise ConfigEntryNotReady(
            f"Unable to connect to device {address} due to {exception}"
        ) from exception

    device = DeviceInfo(
        identifiers={(DOMAIN, address)},
        name=name,
        sw_version=sw_version,
        manufacturer=manufacturer,
        model=model,
    )

    coordinator = GardenaBluetoothCoordinator(
        hass, entry, LOGGER, client, uuids, device, address
    )

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_refresh()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenaBluetoothConfigEntry
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_shutdown()

    return unload_ok
