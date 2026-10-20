"""Coordinator for SteamVR Base Station."""

import logging
from typing import override

from lighthouse_ble import (
    BaseStationV2,
    DeviceInfo,
    LighthouseConnectionError,
    PowerState,
    parse_advertisement,
)

from homeassistant.components.bluetooth import (
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type SteamVRBaseStationConfigEntry = ConfigEntry[SteamVRBaseStationCoordinator]


class SteamVRBaseStationCoordinator(PassiveBluetoothDataUpdateCoordinator):
    """Feeds advertisements to one base station and runs its commands."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SteamVRBaseStationConfigEntry,
        station: BaseStationV2,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            station.address,
            BluetoothScanningMode.PASSIVE,
            connectable=True,
        )
        self.entry = entry
        self.station = station
        self.device_info = device_info

    @callback
    @override
    def _async_handle_unavailable(
        self, service_info: BluetoothServiceInfoBleak
    ) -> None:
        """Log once when the station stops advertising."""
        if self._available:
            _LOGGER.info("%s is unavailable", self.entry.title)
        super()._async_handle_unavailable(service_info)

    @callback
    @override
    def _async_handle_bluetooth_event(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Update the station from an advertisement."""
        if not self._available:
            _LOGGER.info("%s is available again", self.entry.title)
        self.station.set_ble_device(service_info.device)
        if advertisement := parse_advertisement(
            service_info.name, service_info.manufacturer_data
        ):
            self.station.update_from_advertisement(advertisement)
        super()._async_handle_bluetooth_event(service_info, change)

    async def async_set_power(self, target: PowerState) -> None:
        """Switch the station's power and show the result right away."""
        try:
            await self.station.set_power(target)
        except LighthouseConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"name": self.entry.title},
            ) from err
        self.async_update_listeners()
