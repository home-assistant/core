"""Sofar Inverter Modbus — built on modbus-connection.

This module owns the ModbusConnection and the coordinator; sofar-modbus is
the HA-free device library that does the actual register work.

Only the switch platform is wired up so far — this integration is being
added to Core in a sequence of PRs, one platform at a time. PLATFORMS grows
as each subsequent platform lands.
"""

import logging

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sofar_modbus.modern.device import SofarInverter, identify

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MODBUS_ADDR,
    CONF_READ_EPS,
    DEFAULT_MODBUS_ADDR,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Set up Sofar Inverter Modbus from a config entry."""
    connection = ModbusConnection(
        ModbusTcpParams(
            host=entry.data[CONF_HOST],
            port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        )
    )
    entry.async_on_unload(connection.close)

    # The config flow only ever creates an entry after successfully probing
    # and identifying the inverter, so its serial (and thus its type) is
    # always known here — identify() is a pure lookup, not I/O.
    serial = entry.unique_id
    assert serial is not None
    inverter_type, model = identify(serial)

    unit = connection.for_unit(
        int(entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR))
    )
    device = SofarInverter(
        unit, inverter_type=inverter_type, read_eps=entry.data.get(CONF_READ_EPS, False)
    )
    device.prime(serial, model)

    coordinator = SofarDataUpdateCoordinator(
        hass, entry, connection, device, DEFAULT_SCAN_INTERVAL
    )

    # Full refresh (fast + slow tier) before entities exist, so they start
    # with real state instead of "unknown"; also confirms the connection
    # actually works, raising ConfigEntryNotReady otherwise.
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_refresh_slow_tier()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SofarConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
