"""The Hisense AEH-W4A1 integration."""

import ipaddress
import logging

from pyaehw4a1.aehw4a1 import AehW4a1
import pyaehw4a1.exceptions
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


def coerce_ip(value):
    """Validate that provided value is a valid IP address."""
    if not value:
        raise vol.Invalid("Must define an IP address")
    try:
        ipaddress.IPv4Network(value)
    except ValueError as err:
        raise vol.Invalid("Not a valid IP address") from err
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: {
            CLIMATE_DOMAIN: vol.Schema(
                {
                    vol.Optional(CONF_IP_ADDRESS, default=[]): vol.All(
                        cv.ensure_list, [vol.All(cv.string, coerce_ip)]
                    )
                }
            )
        }
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hisense AEH-W4A1 integration."""
    conf = config.get(DOMAIN)
    hass.data[DOMAIN] = {}

    if conf is not None:
        devices = conf[CONF_IP_ADDRESS][:]
        for device in devices:
            try:
                await AehW4a1(device).check()
            except pyaehw4a1.exceptions.ConnectionError:
                conf[CONF_IP_ADDRESS].remove(device)
                _LOGGER.warning("Hisense AEH-W4A1 at %s not found", device)
        if conf[CONF_IP_ADDRESS]:
            hass.data[DOMAIN] = conf
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Hisense AEH-W4A1."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
