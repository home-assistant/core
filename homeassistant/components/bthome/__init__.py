"""The BTHome Bluetooth integration."""
from __future__ import annotations

import logging

from bthome_ble import BTHomeBluetoothDeviceData, SensorUpdate
from bthome_ble.parser import EncryptionScheme

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def process_service_info(
    hass: HomeAssistant,
    entry: ConfigEntry,
    data: BTHomeBluetoothDeviceData,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    update = data.update(service_info)
    # If that payload was encrypted and the bindkey was not verified then we need to reauth
    if data.encryption_scheme != EncryptionScheme.NONE and not data.bindkey_verified:
        entry.async_start_reauth(hass, data={"device": data})

    return update


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BTHome Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None

    kwargs = {}
    if bindkey := entry.data.get("bindkey"):
        kwargs["bindkey"] = bytes.fromhex(bindkey)
    data = BTHomeBluetoothDeviceData(**kwargs)

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=lambda service_info: process_service_info(
            hass, entry, data, service_info
        ),
        connectable=False,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        coordinator.async_start()
    )  # only start after all platforms have had a chance to subscribe
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
