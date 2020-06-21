"""Fortigate integration."""
import logging

from pyFGT.fortigate import FGTConnectionError, FortiGate
import voluptuous as vol

from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_HOST,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "fortigate"

DATA_FGT = DOMAIN

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN, invalidation_version="0.112.0"),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_API_KEY): cv.string,
                    vol.Optional(CONF_DEVICES, default=[]): vol.All(
                        cv.ensure_list, [cv.string]
                    ),
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Start the Fortigate component."""
    conf = config[DOMAIN]

    host = conf[CONF_HOST]
    user = conf[CONF_USERNAME]
    api_key = conf[CONF_API_KEY]
    devices = conf[CONF_DEVICES]

    is_success = await async_setup_fortigate(hass, config, host, user, api_key, devices)

    return is_success


async def async_setup_fortigate(hass, config, host, user, api_key, devices):
    """Start up the Fortigate component platforms."""
    fgt = FortiGate(host, user, apikey=api_key, disable_request_warnings=True)

    try:
        fgt.login()
    except FGTConnectionError:
        _LOGGER.error("Failed to connect to Fortigate")
        return False

    hass.data[DATA_FGT] = {"fgt": fgt, "devices": devices}

    hass.async_create_task(
        async_load_platform(hass, "device_tracker", DOMAIN, {}, config)
    )

    async def close_fgt(event):
        """Close Fortigate connection on HA Stop."""
        fgt.logout()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_fgt)

    return True
