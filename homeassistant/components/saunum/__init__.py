"""The Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_DEVICE_ID, PLATFORMS
from .coordinator import LeilSaunaCoordinator

_LOGGER = logging.getLogger(__name__)

type LeilSaunaConfigEntry = ConfigEntry[LeilSaunaCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Set up Saunum Leil Sauna from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    device_id = DEFAULT_DEVICE_ID

    client = AsyncModbusTcpClient(host=host, port=port, timeout=5)

    # Test connection
    try:
        await client.connect()
        if not client.connected:
            raise ConfigEntryNotReady(f"Unable to connect to {host}:{port}")
    except ModbusException as exc:
        raise ConfigEntryNotReady(f"Error connecting to {host}:{port}: {exc}") from exc

    coordinator = LeilSaunaCoordinator(hass, client, device_id, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LeilSaunaConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        coordinator.client.close()

    return unload_ok
