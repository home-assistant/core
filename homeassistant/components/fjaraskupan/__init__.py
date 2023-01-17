"""The Fjäråskupan integration."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
import logging

from fjaraskupan import Device, State

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_address_present,
    async_ble_device_from_address,
    async_rediscover_address,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DISPATCH_DETECTION, DOMAIN


class UnableToConnect(HomeAssistantError):
    """Exception to indicate that we can not connect to device."""


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


class Coordinator(DataUpdateCoordinator[State]):
    """Update coordinator for each device."""

    def __init__(
        self, hass: HomeAssistant, device: Device, device_info: DeviceInfo
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        self.device_info = device_info
        self._refresh_was_scheduled = False

        super().__init__(
            hass, _LOGGER, name="Fjäråskupan", update_interval=timedelta(seconds=120)
        )

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        self._refresh_was_scheduled = scheduled
        await super()._async_refresh(
            log_failures=log_failures,
            raise_on_auth_failed=raise_on_auth_failed,
            scheduled=scheduled,
            raise_on_entry_error=raise_on_entry_error,
        )

    async def _async_update_data(self) -> State:
        """Handle an explicit update request."""
        if self._refresh_was_scheduled:
            if async_address_present(self.hass, self.device.address, False):
                return self.device.state
            raise UpdateFailed(
                "No data received within schedule, and device is no longer present"
            )

        if (
            ble_device := async_ble_device_from_address(
                self.hass, self.device.address, True
            )
        ) is None:
            raise UpdateFailed("No connectable path to device")
        async with self.device.connect(ble_device) as device:
            await device.update()
        return self.device.state

    def detection_callback(self, service_info: BluetoothServiceInfoBleak) -> None:
        """Handle a new announcement of data."""
        self.device.detection_callback(service_info.device, service_info.advertisement)
        self.async_set_updated_data(self.device.state)

    @asynccontextmanager
    async def async_connect_and_update(self) -> AsyncIterator[Device]:
        """Provide an up to date device for use during connections."""
        if (
            ble_device := async_ble_device_from_address(
                self.hass, self.device.address, True
            )
        ) is None:
            raise UnableToConnect("No connectable path to device")

        async with self.device.connect(ble_device) as device:
            yield device

        self.async_set_updated_data(self.device.state)


@dataclass
class EntryState:
    """Store state of config entry."""

    coordinators: dict[str, Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fjäråskupan from a config entry."""

    state = EntryState({})
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = state

    def detection_callback(
        service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        if change != BluetoothChange.ADVERTISEMENT:
            return
        if data := state.coordinators.get(service_info.address):
            _LOGGER.debug("Update: %s", service_info)
            data.detection_callback(service_info)
        else:
            _LOGGER.debug("Detected: %s", service_info)

            device = Device(service_info.device.address)
            device_info = DeviceInfo(
                connections={(dr.CONNECTION_BLUETOOTH, service_info.address)},
                identifiers={(DOMAIN, service_info.address)},
                manufacturer="Fjäråskupan",
                name="Fjäråskupan",
            )

            coordinator: Coordinator = Coordinator(hass, device, device_info)
            coordinator.detection_callback(service_info)

            state.coordinators[service_info.address] = coordinator
            async_dispatcher_send(
                hass, f"{DISPATCH_DETECTION}.{entry.entry_id}", coordinator
            )

    entry.async_on_unload(
        async_register_callback(
            hass,
            detection_callback,
            BluetoothCallbackMatcher(
                manufacturer_id=20296,
                manufacturer_data_start=[79, 68, 70, 74, 65, 82],
                connectable=False,
            ),
            BluetoothScanningMode.ACTIVE,
        )
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


@callback
def async_setup_entry_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    constructor: Callable[[Coordinator], list[Entity]],
) -> None:
    """Set up a platform with added entities."""

    entry_state: EntryState = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for coordinator in entry_state.coordinators.values()
        for entity in constructor(coordinator)
    )

    @callback
    def _detection(coordinator: Coordinator) -> None:
        async_add_entities(constructor(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DISPATCH_DETECTION}.{entry.entry_id}", _detection
        )
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        for device_entry in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        ):
            for conn in device_entry.connections:
                if conn[0] == dr.CONNECTION_BLUETOOTH:
                    async_rediscover_address(hass, conn[1])

    return unload_ok
