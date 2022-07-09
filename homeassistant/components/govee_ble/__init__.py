"""The Govee Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .govee_parser import parse_govee_from_discovery_data

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None
    # TODO: coordinator is not a good design here since
    # there can be multiple sensors on the device and we
    # need to handle each one separately, we need some type of dispatcher
    # to dynamically add sensors and feed updates to the right sensor
    coordinator: DataUpdateCoordinator[dict[str, Any]] = DataUpdateCoordinator(
        hass, _LOGGER, name=entry.title, update_interval=None
    )

    @callback
    def _async_update_govee_device(
        service_info: bluetooth.BluetoothServiceInfo, change: bluetooth.BluetoothChange
    ) -> None:
        """Subscribe to bluetooth changes."""
        if data := parse_govee_from_discovery_data(
            service_info.manufacturer_data,
        ):
            data["rssi"] = service_info.rssi
            coordinator.async_set_updated_data(data)

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            _async_update_govee_device,
            bluetooth.BluetoothCallbackMatcher(address=address),
        )
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
