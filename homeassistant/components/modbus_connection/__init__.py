"""The Modbus Connection integration."""

from collections.abc import Mapping
from typing import Any, cast

from modbus_connection import ModbusConnection, ModbusError, ModbusUnit
from modbus_connection.tmodbus import connect_serial, connect_tcp

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONNECTION_SERIAL,
    DOMAIN,
)
from .exceptions import ConnectionNotReady

__all__ = ["ConnectionNotReady", "async_get_unit"]

type ModbusConnectionConfigEntry = ConfigEntry[ModbusConnection]


async def _async_open(data: Mapping[str, Any]) -> ModbusConnection:
    """Open the connection described by ``data`` (transport parameters).

    Shared by config-entry setup and the config flow's validation; the caller
    owns the returned connection and closes it.
    """
    if data[CONF_TYPE] == CONNECTION_SERIAL:
        return await connect_serial(
            data[CONF_DEVICE],
            baudrate=data[CONF_BAUDRATE],
            bytesize=data[CONF_BYTESIZE],
            parity=data[CONF_PARITY],
            stopbits=data[CONF_STOPBITS],
        )
    return await connect_tcp(data[CONF_HOST], port=data[CONF_PORT])


async def async_setup_entry(
    hass: HomeAssistant, entry: ModbusConnectionConfigEntry
) -> bool:
    """Set up a Modbus connection from a config entry."""
    try:
        connection = await _async_open(entry.data)
    except ModbusError as err:
        raise ConfigEntryNotReady(f"Could not open Modbus connection: {err}") from err

    entry.runtime_data = connection

    # The connection is transient and does not self-reconnect: on a drop, reload
    # this entry. HA's ConfigEntryNotReady retry is the reconnect backoff.
    entry.async_on_unload(
        connection.on_connection_lost(
            lambda: hass.config_entries.async_schedule_reload(entry.entry_id)
        )
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ModbusConnectionConfigEntry
) -> bool:
    """Unload a config entry and close the owned connection."""
    await entry.runtime_data.close()
    return True


@callback
def async_get_unit(
    hass: HomeAssistant, connection_entry_id: str, unit_id: int
) -> ModbusUnit:
    """Return a Modbus unit on a shared connection.

    Consumer integrations call this to borrow a ``ModbusUnit`` bound to their
    unit ID; the ``ModbusConnection`` itself never leaves this integration.

    Raises ``ValueError`` if ``connection_entry_id`` does not point at a
    ``modbus_connection`` entry (a programming error in the consumer). Raises
    ``ConnectionNotReady`` if that entry is missing or not loaded; it is a
    ``ConfigEntryNotReady``, so a consumer can let it propagate from its own
    ``async_setup_entry`` to get Home Assistant's setup retry.
    """
    entry = cast(
        "ModbusConnectionConfigEntry | None",
        hass.config_entries.async_get_entry(connection_entry_id),
    )
    if entry is not None and entry.domain != DOMAIN:
        raise ValueError(f"{connection_entry_id} is not a modbus_connection entry")
    if entry is None or entry.state is not ConfigEntryState.LOADED:
        raise ConnectionNotReady(connection_entry_id)
    return entry.runtime_data.for_unit(unit_id)
