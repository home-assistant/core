"""The KWB Modbus integration."""

from __future__ import annotations

import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]
# _PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.SWITCH, Platform.BUTTON]

type KwbModbusConfigEntry = ConfigEntry[AsyncModbusTcpClient]


async def async_setup_entry(hass: HomeAssistant, entry: KwbModbusConfigEntry) -> bool:
    """Set up KWB Modbus from a config entry."""

    # create Async Modbus TCP client
    client = AsyncModbusTcpClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        timeout=10,
    )

    # Test connection
    try:
        await client.connect()
        if not client.connected:
            raise ConfigEntryNotReady(
                f"Could not connect to KWB Modbus at {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
            )

        # Test basic communication
        result = await client.read_input_registers(address=8204, count=1)
        if result.isError():
            raise ConfigEntryNotReady(
                f"Error reading holding registers from KWB Modbus at {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
            )
    except ModbusException as err:
        raise ConfigEntryNotReady(f"Modbus connection failed: {err}") from err
    finally:
        if client.connected:
            client.close()

    # Store client for platforms
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KwbModbusConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.runtime_data and entry.runtime_data.connected:
        entry.runtime_data.close()

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
