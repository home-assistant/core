"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging

from pymodbus.exceptions import ModbusException
from pystiebeleltron import StiebelEltronModbusError, get_controller_model

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DEFAULT_PORT, DOMAIN
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
        model = await get_controller_model(host, port)
    except ModbusException as exception:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from exception
    except StiebelEltronModbusError as exception:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="modbus_data_error",
        ) from exception

    coordinator = StiebelEltronDataCoordinator(hass, entry, model, host, port)

    entry.runtime_data = coordinator
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: StiebelEltronConfigEntry,
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, _PLATFORMS):
        await entry.runtime_data.close()
    return unload_ok
