"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging

from modbus_connection import ModbusError
from modbus_connection.pymodbus import connect_tcp
from pystiebeleltron import StiebelEltronModbusError, get_controller_model

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DEFAULT_PORT, DEVICE_ID
from .coordinator import StiebelEltronConfigEntry, StiebelEltronDataCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    try:
        connection = await connect_tcp(host, port=port)
    except ModbusError as exception:
        raise ConfigEntryNotReady("Could not connect to device") from exception
    entry.async_on_unload(connection.close)

    try:
        model = await get_controller_model(connection.for_unit(DEVICE_ID))
    except StiebelEltronModbusError as exception:
        raise ConfigEntryNotReady("Could not read controller model") from exception

    coordinator = StiebelEltronDataCoordinator(hass, entry, model, connection, host)

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(
        connection.on_connection_lost(
            lambda: hass.config_entries.async_schedule_reload(entry.entry_id)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
