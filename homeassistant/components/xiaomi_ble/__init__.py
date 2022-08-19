"""The Xiaomi Bluetooth integration."""
from __future__ import annotations

import logging

from xiaomi_ble import SensorUpdate, XiaomiBluetoothDeviceData
from xiaomi_ble.parser import EncryptionScheme

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def process_service_info(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    data: XiaomiBluetoothDeviceData,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    """Process a BluetoothServiceInfoBleak, running side effects and returning sensor data."""
    update = data.update(service_info)

    # If device isn't pending we know it has seen at least one broadcast with a payload
    # If that payload was encrypted and the bindkey was not verified then we need to reauth
    if (
        not data.pending
        and data.encryption_scheme != EncryptionScheme.NONE
        and not data.bindkey_verified
    ):
        entry.async_start_reauth(hass, data={"device": data})

    return update


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Xiaomi BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None

    kwargs = {}
    if bindkey := entry.data.get("bindkey"):
        kwargs["bindkey"] = bytes.fromhex(bindkey)
    data = XiaomiBluetoothDeviceData(**kwargs)

    def _needs_poll(
        service_info: BluetoothServiceInfoBleak, last_poll: float | None
    ) -> bool:
        return data.poll_needed(service_info, last_poll)

    async def _async_poll(service_info: BluetoothServiceInfoBleak):
        # BluetoothServiceInfoBleak is defined in HA, otherwise would just pass it
        # directly to the Xiaomi code
        return await data.async_poll(service_info.device)

    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = ActiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.PASSIVE,
        update_method=lambda service_info: process_service_info(
            hass, entry, data, service_info
        ),
        needs_poll_method=_needs_poll,
        poll_method=_async_poll,
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
