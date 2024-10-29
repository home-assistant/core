"""The Fjäråskupan integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from fjaraskupan import Device

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_rediscover_address,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPATCH_DETECTION, DOMAIN
from .coordinator import FjaraskupanCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)


@dataclass
class EntryState:
    """Store state of config entry."""

    coordinators: dict[str, FjaraskupanCoordinator]


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

            coordinator: FjaraskupanCoordinator = FjaraskupanCoordinator(
                hass, device, device_info
            )
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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


@callback
def async_setup_entry_platform(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    constructor: Callable[[FjaraskupanCoordinator], list[Entity]],
) -> None:
    """Set up a platform with added entities."""

    entry_state: EntryState = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for coordinator in entry_state.coordinators.values()
        for entity in constructor(coordinator)
    )

    @callback
    def _detection(coordinator: FjaraskupanCoordinator) -> None:
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
