"""The Govee Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .bluetooth_update_coordinator import BluetoothDataUpdateCoordinator
from .const import DOMAIN
from .govee_parser import parse_govee_from_discovery_data

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Bluetooth from a config entry."""
    address = entry.unique_id
    assert address is not None

    @callback
    def _async_parse_govee_device(
        service_info: bluetooth.BluetoothServiceInfo, change: bluetooth.BluetoothChange
    ) -> dict[str, Any] | None:
        """Subscribe to bluetooth changes."""
        if data := parse_govee_from_discovery_data(
            service_info.manufacturer_data,
        ):
            data["rssi"] = service_info.rssi
            _LOGGER.warning("Parser returned data: %s", data)
            return data
        return None

    coordinator = BluetoothDataUpdateCoordinator(
        hass,
        _LOGGER,
        name=entry.title,
        address=address,
        parser_method=_async_parse_govee_device,
    )
    entry.async_on_unload(coordinator.async_setup())
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
