"""The IKEA Idasen Desk integration."""
from __future__ import annotations

import logging

from attr import dataclass
from bleak.exc import BleakError
from idasen_ha import Desk
from idasen_ha.errors import AuthFailedError

from homeassistant.components import bluetooth
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

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.COVER]

_LOGGER = logging.getLogger(__name__)


class IdasenDeskCoordinator(DataUpdateCoordinator[int | None]):
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

        self.desk = Desk(self.async_set_updated_data)

    async def async_connect(self) -> bool:
        """Connect to desk."""
        _LOGGER.debug("Trying to connect %s", self._address)
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self._address, connectable=True
        )
        if ble_device is None:
            return False
        self._expected_connected = True
        await self.desk.connect(ble_device)
        return True

    async def async_disconnect(self) -> None:
        """Disconnect from desk."""
        _LOGGER.debug("Disconnecting from %s", self._address)
        self._expected_connected = False
        await self.desk.disconnect()

    @callback
    def async_set_updated_data(self, data: int | None) -> None:
        """Handle data update."""
        if self._expected_connected:
            if not self.desk.is_connected:
                _LOGGER.debug("Desk disconnected. Reconnecting")
                self.hass.async_create_task(self.async_connect())
        elif self.desk.is_connected:
            _LOGGER.warning("Desk is connected but should not be. Disconnecting")
            self.hass.async_create_task(self.desk.disconnect())
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
