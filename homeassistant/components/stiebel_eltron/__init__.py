"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

from modbus_connection import ModbusTcpParams
from pystiebeleltron import StiebelEltronModbusError, get_controller_model

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)

from .const import DEFAULT_PORT, UNIT_ID
from .coordinator import StiebelEltronConfigEntry, StiebelEltronDataCoordinator

_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)

    try:
        unit = async_get_unit(
            hass, entry, ModbusTcpParams(host=host, port=port), UNIT_ID
        )
    # Another integration already holds this host and port with link settings
    # that cannot be honoured on one connection.
    except HomeAssistantError as exception:
        raise ConfigEntryError(str(exception)) from exception

    try:
        model = await get_controller_model(unit)
    except StiebelEltronModbusError as exception:
        raise ConfigEntryNotReady("Could not read controller model") from exception

    coordinator = StiebelEltronDataCoordinator(hass, entry, model, unit, host)

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
