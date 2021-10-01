"""The Fjäråskupan integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

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

PLATFORMS = ["binary_sensor", "fan", "light", "sensor"]

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
    ) -> None:
        if not device_filter(ble_device, advertisement_data):
            return

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

            coordinator: DataUpdateCoordinator[State] = DataUpdateCoordinator(
                hass,
                logger=_LOGGER,
                name="Fjaraskupan Updater",
                update_interval=timedelta(seconds=120),
                update_method=async_update_data,
            )
            coordinator.async_set_updated_data(device.state)

            device_info: DeviceInfo = {
                "identifiers": {(DOMAIN, ble_device.address)},
                "manufacturer": "Fjäråskupan",
                "name": "Fjäråskupan",
            }
            device_state = DeviceState(device, coordinator, device_info)
            state.devices[ble_device.address] = device_state
            async_dispatcher_send(
                hass, f"{DISPATCH_DETECTION}.{entry.entry_id}", device_state
            )

    scanner.register_detection_callback(detection_callback)
    await scanner.start()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


@callback
def async_setup_entry_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    constructor: Callable[[DeviceState], list[Entity]],
) -> None:
    """Set up a platform with added entities."""

    entry_state: EntryState = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for device_state in entry_state.devices.values()
        for entity in constructor(device_state)
    )

    @callback
    def _detection(device_state: DeviceState) -> None:
        async_add_entities(constructor(device_state))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DISPATCH_DETECTION}.{entry.entry_id}", _detection
        )
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_state: EntryState = hass.data[DOMAIN].pop(entry.entry_id)
        await entry_state.scanner.stop()

    return unload_ok
