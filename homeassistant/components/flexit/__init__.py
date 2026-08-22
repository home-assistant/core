"""The Flexit component, for AC units with a CI66 Modbus adapter."""

import logging

from modbus_connection import ModbusConnection, ModbusError
from modbus_connection.pymodbus import connect_serial, connect_tcp

from homeassistant.const import (
    CONF_DEVICE,
    CONF_HOST,
    CONF_PORT,
    CONF_SLAVE,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_PORT,
    TYPE_SERIAL,
)
from .coordinator import FlexitConfigEntry, FlexitDataCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def _async_connect(entry: FlexitConfigEntry) -> ModbusConnection:
    """Open the Modbus connection matching the config entry's connection type."""
    if entry.data[CONF_TYPE] == TYPE_SERIAL:
        return await connect_serial(
            entry.data[CONF_DEVICE],
            baudrate=entry.data[CONF_BAUDRATE],
            bytesize=entry.data[CONF_BYTESIZE],
            parity=entry.data[CONF_PARITY],
            stopbits=entry.data[CONF_STOPBITS],
        )
    return await connect_tcp(
        entry.data[CONF_HOST], port=entry.data.get(CONF_PORT, DEFAULT_PORT)
    )


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Set up Flexit from a config entry."""

    slave = entry.data[CONF_SLAVE]

    try:
        connection = await _async_connect(entry)
    except ModbusError as exception:
        raise ConfigEntryNotReady("Could not connect to device") from exception
    entry.async_on_unload(connection.close)

    host = entry.data.get(CONF_HOST)
    coordinator = FlexitDataCoordinator(hass, entry, connection, slave, host)

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
    entry: FlexitConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
