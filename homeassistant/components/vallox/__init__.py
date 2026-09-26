"""Support for Vallox ventilation units."""

import ipaddress

import probatio
from vallox_websocket_api import Vallox

from homeassistant.const import CONF_HOST, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = probatio.Schema(
    probatio.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: probatio.Schema(
                {
                    probatio.Required(CONF_HOST): probatio.All(
                        ipaddress.ip_address, cv.string
                    ),
                    probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                }
            )
        },
    ),
    extra=probatio.ALLOW_EXTRA,
)

PLATFORMS: list[str] = [
    Platform.BINARY_SENSOR,
    Platform.DATE,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Vallox integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ValloxConfigEntry) -> bool:
    """Set up the client and boot the platforms."""
    host = entry.data[CONF_HOST]

    client = Vallox(host)

    coordinator = ValloxDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ValloxConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
