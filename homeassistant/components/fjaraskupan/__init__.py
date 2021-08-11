"""The Fjäråskupan integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Callable

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from fjaraskupan import Device, State, device_filter

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DISPATCH_DETECTION, DOMAIN

PLATFORMS = ["fan"]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeviceState:
    """Store state of a device."""

    device: Device
    coordinator: DataUpdateCoordinator[State]
    device_info: DeviceInfo


@dataclass
class EntryState:
    """Store state of config entry."""

    scanner: BleakScanner
    devices: dict[str, DeviceState]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fjäråskupan from a config entry."""

    scanner = BleakScanner()

    state = EntryState(scanner, {})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = state

    async def detection_callback(
        ble_device: BLEDevice, advertisement_data: AdvertisementData
    ):
        if device_filter(ble_device, advertisement_data):
            _LOGGER.debug(
                "Detection: %s %s - %s", ble_device.name, ble_device, advertisement_data
            )

            data = state.devices.get(ble_device.address)

            if data:
                data.device.detection_callback(ble_device, advertisement_data)
                data.coordinator.async_set_updated_data(data.device.state)
            else:

                device = Device(ble_device)
                device.detection_callback(ble_device, advertisement_data)

                async def async_update_data():
                    """Handle an explicit update request."""
                    await device.update()
                    return device.state

                coordinator = DataUpdateCoordinator[State](
                    hass,
                    logger=_LOGGER,
                    name="Fjäråskupan Updater",
                    update_interval=timedelta(seconds=120),
                    update_method=async_update_data,
                )
                coordinator.async_set_updated_data(device.state)

                device_info: DeviceInfo = {
                    "identifiers": {(DOMAIN, ble_device.address)},
                    "manufacturer": "Fjäråskupan",
                    "name": "Fjäråskupan",
                }
                data = DeviceState(device, coordinator, device_info)
                state.devices[ble_device.address] = data
                async_dispatcher_send(
                    hass, DISPATCH_DETECTION, entry.entry_id, ble_device.address
                )

    scanner.register_detection_callback(detection_callback)
    await scanner.start()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_setup_entry_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    constructor: Callable[[DeviceState], list[Entity]],
) -> None:
    """Set up a platform with added entities."""

    entrystate: EntryState = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            entity
            for devicestate in entrystate.devices.values()
            for entity in constructor(devicestate)
        ]
    )

    @callback
    def _detection(entry_id: str, address: str):
        if entry_id != entry.entry_id:
            return
        devicestate = entrystate.devices[address]
        async_add_entities(constructor(devicestate))

    entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DETECTION, _detection)
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entrystate: EntryState = hass.data[DOMAIN].pop(entry.entry_id)
        await entrystate.scanner.stop()

    return unload_ok
