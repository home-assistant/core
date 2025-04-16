"""The Airios integration."""

from __future__ import annotations

import logging

from pyairios import Airios, AiriosRtuTransport, AiriosTcpTransport

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_SCAN_INTERVAL, BridgeType
from .coordinator import AiriosDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.FAN,
]


type AiriosConfigEntry = ConfigEntry[AiriosDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AiriosConfigEntry) -> bool:
    """Set up Airios from a config entry."""

    bridge_type = entry.data[CONF_TYPE]
    if bridge_type == BridgeType.SERIAL:
        device = entry.data[CONF_DEVICE]
        transport = AiriosRtuTransport(device)
    elif bridge_type == BridgeType.NETWORK:
        host = entry.data[CONF_HOST]
        port = entry.data[CONF_PORT]
        transport = AiriosTcpTransport(host, port)
    else:
        raise ConfigEntryNotReady(f"Unexpected bridge type {bridge_type}")

    modbus_address = entry.data[CONF_ADDRESS]
    api = Airios(transport, modbus_address)

    update_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = AiriosDataUpdateCoordinator(hass, api, update_interval)
    await coordinator.async_config_entry_first_refresh()

    bridge_rf_address = await api.bridge.node_rf_address()
    if bridge_rf_address is None or bridge_rf_address.value is None:
        raise ConfigEntryNotReady("Failed to get bridge RF address")
    bridge_rf_address = bridge_rf_address.value

    if entry.unique_id != str(bridge_rf_address):
        message = (
            f"Unexpected device {bridge_rf_address} found, expected {entry.unique_id}"
        )
        _LOGGER.error(message)
        raise ConfigEntryNotReady(message)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AiriosConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: AiriosDataUpdateCoordinator = entry.runtime_data
        coordinator.api.close()
    return unload_ok
