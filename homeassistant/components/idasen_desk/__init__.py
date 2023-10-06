"""The IKEA Idasen Desk integration."""
from __future__ import annotations

import logging

from attr import dataclass
from bleak import BleakError
from idasen_ha import Desk

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    CONF_ADDRESS,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.COVER]

_LOGGER = logging.getLogger(__name__)


@dataclass
class DeskData:
    """Data for the Idasen Desk integration."""

    desk: Desk
    address: str
    device_info: DeviceInfo
    coordinator: DataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IKEA Idasen from a config entry."""
    address: str = entry.data[CONF_ADDRESS].upper()

    coordinator: DataUpdateCoordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
    )

    desk = Desk(coordinator.async_set_updated_data)
    device_info = DeviceInfo(
        name=entry.title,
        connections={(dr.CONNECTION_BLUETOOTH, address)},
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = DeskData(
        desk, address, device_info, coordinator
    )

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    try:
        await desk.connect(ble_device)
    except (TimeoutError, BleakError) as ex:
        raise ConfigEntryNotReady(f"Unable to connect to desk {address}") from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _async_stop(event: Event) -> None:
        """Close the connection."""
        await desk.disconnect()

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
        await data.desk.disconnect()

    return unload_ok
