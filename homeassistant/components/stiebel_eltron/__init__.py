"""The component for STIEBEL ELTRON heat pumps with ISGWeb Modbus module."""

import logging

from pystiebeleltron import StiebelEltronModbusError, get_controller_model
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DEVICE_DEFAULT_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv

from .const import CONF_HUB, DEFAULT_HUB, DOMAIN
from .coordinator import StiebelEltronConfigEntry, StiebelEltronDataCoordinator

MODBUS_DOMAIN = "modbus"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(
    hass: HomeAssistant, entry: StiebelEltronConfigEntry
) -> bool:
    """Set up STIEBEL ELTRON from a config entry."""

    host = str(entry.data.get(CONF_HOST))
    port_data = entry.data.get(CONF_PORT)
    port = int(port_data) if port_data is not None else 502

    try:
        model = await get_controller_model(host, port)
    except StiebelEltronModbusError as exception:
        raise ConfigEntryError(exception) from exception

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
    coordinator = entry.runtime_data
    await coordinator.close()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
