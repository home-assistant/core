"""The KWB Modbus integration."""

from __future__ import annotations

import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_DISCOVERED_SENSORS, DEFAULT_SCAN_INTERVAL
from .coordinator import KWBDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.NUMBER,
]

type KwbModbusConfigEntry = ConfigEntry[KWBDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KwbModbusConfigEntry) -> bool:
    """Set up KWB Modbus from a config entry."""
    client = AsyncModbusTcpClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        timeout=10,
    )
    try:
        await client.connect()
        if not client.connected:
            raise ConfigEntryNotReady(
                f"Could not connect to KWB at {entry.data[CONF_HOST]}:{entry.data[CONF_PORT]}"
            )
        result = await client.read_input_registers(address=8192, count=1)
        if result.isError():
            raise ConfigEntryNotReady("Error during Modbus test read")
    except ModbusException as err:
        raise ConfigEntryNotReady(f"Modbus error: {err}") from err
    # NOTE: Do NOT close the client — coordinator keeps it open

    coordinator = KWBDataUpdateCoordinator(
        hass=hass,
        client=client,
        entry=entry,
        scan_interval=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    # Run discovery if this is the first start (discovered_sensors is empty dict)
    if entry.data.get(CONF_DISCOVERED_SENSORS) == {}:
        await coordinator.async_run_discovery()

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KwbModbusConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: KWBDataUpdateCoordinator = entry.runtime_data
    if coordinator.client.connected:
        coordinator.client.close()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
