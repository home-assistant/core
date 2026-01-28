"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging

from pymodbus.client import ModbusTcpClient
from pystiebeleltron.pystiebeleltron import StiebelEltronAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CLIMATE]


type StiebelEltronConfigEntry = ConfigEntry[StiebelEltronAPI]


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""
    client = StiebelEltronAPI(
        ModbusTcpClient(entry.data[CONF_HOST], port=entry.data[CONF_PORT]), 1
    )

    success = await hass.async_add_executor_job(client.update)
    if not success:
        raise ConfigEntryNotReady("Could not connect to device")

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
