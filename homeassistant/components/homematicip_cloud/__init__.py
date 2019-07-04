"""Support for HomematicIP Cloud devices."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .config_flow import configured_haps
from .const import (
    CONF_ACCESSPOINT, CONF_AUTHTOKEN, DOMAIN, HMIPC_AUTHTOKEN, HMIPC_HAPID,
    HMIPC_NAME)
from .device import HomematicipGenericDevice  # noqa: F401
from .hap import HomematicipAuth, HomematicipHAP  # noqa: F401

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN, default=[]): vol.All(cv.ensure_list, [vol.Schema({
        vol.Optional(CONF_NAME, default=''): vol.Any(cv.string),
        vol.Required(CONF_ACCESSPOINT): cv.string,
        vol.Required(CONF_AUTHTOKEN): cv.string,
    })]),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomematicIP Cloud component."""
    hass.data[DOMAIN] = {}

    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in configured_haps(hass):
            hass.async_add_job(hass.config_entries.flow.async_init(
                DOMAIN, context={'source': config_entries.SOURCE_IMPORT},
                data={
                    HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                    HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                    HMIPC_NAME: conf[CONF_NAME],
                }
            ))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an access point from a config entry."""
    hap = HomematicipHAP(hass, entry)
    hapid = entry.data[HMIPC_HAPID].replace('-', '').upper()
    hass.data[DOMAIN][hapid] = hap

    if not await hap.async_setup():
        return False

    # Register hap as device in registry.
    device_registry = await dr.async_get_registry(hass)
    home = hap.home
    # Add the HAP name from configuration if set.
    hapname = home.label \
        if not home.name else "{} {}".format(home.label, home.name)
    device_registry.async_get_or_create(
        config_entry_id=home.id,
        identifiers={(DOMAIN, home.id)},
        manufacturer='eQ-3',
        name=hapname,
        model=home.modelType,
        sw_version=home.currentAPVersion,
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hap = hass.data[DOMAIN].pop(entry.data[HMIPC_HAPID])
    return await hap.async_reset()
