"""The IKEA Idasen Desk integration."""

from __future__ import annotations

import asyncio
import logging

from attr import dataclass
from bleak.exc import BleakError
from idasen_ha import Desk
from idasen_ha.errors import AuthFailedError

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.match import ADDRESS, BluetoothCallbackMatcher
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_ADDRESS,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


class IdasenDeskCoordinator(DataUpdateCoordinator[int | None]):  # pylint: disable=hass-enforce-coordinator-module
    """Class to manage updates for the Idasen Desk."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        address: str,
    ) -> None:
        """Init IdasenDeskCoordinator."""

        super().__init__(hass, logger, name=name)
        self._address = address
        self._expected_connected = False
        self._connection_lost = False
        self._disconnect_lock = asyncio.Lock()

        self.desk = Desk(self.async_set_updated_data)

    async def async_connect(self) -> bool:
        """Connect to desk."""
        _LOGGER.debug("Trying to connect %s", self._address)
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            _LOGGER.debug("No BLEDevice for %s", self._address)
            return False
        self._expected_connected = True
        await self.desk.connect(ble_device)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from desk."""
        _LOGGER.debug("Disconnecting from %s", self._address)
        self._expected_connected = False
        self._connection_lost = False
        await self.desk.disconnect()

    async def async_ensure_connection_state(self) -> None:
        """Check if the expected connection state matches the current state.

        If the expected and current state don't match, calls connect/disconnect
        as needed.
        """
        if self._expected_connected:
            if not self.desk.is_connected:
                _LOGGER.debug("Desk disconnected. Reconnecting")
                self._connection_lost = True
                await self.async_connect()
            elif self._connection_lost:
                _LOGGER.info("Reconnected to desk")
                self._connection_lost = False
        elif self.desk.is_connected:
            if self._disconnect_lock.locked():
                _LOGGER.debug("Already disconnecting")
                return
            async with self._disconnect_lock:
                _LOGGER.debug("Desk is connected but should not be. Disconnecting")
                await self.desk.disconnect()

    @callback
    def async_set_updated_data(self, data: int | None) -> None:
        """Handle data update."""
        self.hass.async_create_task(self.async_ensure_connection_state())
        return super().async_set_updated_data(data)


@dataclass
class DeskData:
    """Data for the Idasen Desk integration."""

    address: str
    device_info: DeviceInfo
    coordinator: IdasenDeskCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IKEA Idasen from a config entry."""
    address: str = entry.data[CONF_ADDRESS].upper()

    coordinator = IdasenDeskCoordinator(hass, _LOGGER, entry.title, address)
    device_info = DeviceInfo(
        name=entry.title,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = DeskData(
        address, device_info, coordinator
    )

    try:
        if not await coordinator.async_connect():
            raise ConfigEntryNotReady(f"Unable to connect to desk {address}")
    except (AuthFailedError, TimeoutError, BleakError, Exception) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to desk {address}") from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _async_bluetooth_callback(
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Update from a Bluetooth callback to ensure that a new BLEDevice is fetched."""
        _LOGGER.debug("Bluetooth callback triggered")
        hass.async_create_task(coordinator.async_ensure_connection_state())

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_bluetooth_callback,
            BluetoothCallbackMatcher({ADDRESS: address}),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )
    )

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await coordinator.async_disconnect()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    data: DeskData = hass.data[DOMAIN][entry.entry_id]
    if entry.title != data.device_info[ATTR_NAME]:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data: DeskData = hass.data[DOMAIN].pop(entry.entry_id)
        await data.coordinator.async_disconnect()
        bluetooth.async_rediscover_address(hass, data.address)

    return unload_ok
