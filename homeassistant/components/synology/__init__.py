"""The synology component."""

from functools import partial
import logging

import requests
from synology.surveillance_station import SurveillanceStation
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONF_WHITELIST,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    DATA_NAME,
    DATA_SURVEILLANCE_CLIENT,
    DATA_VERIFY_SSL,
    DEFAULT_NAME,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    DOMAIN_DATA,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_WHITELIST_SCHEMA = vol.Schema(
    {CONF_WHITELIST: vol.Schema({vol.Optional("camera", default=[]): cv.ensure_list})}
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_URL): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
                vol.Optional(CONF_WHITELIST, default={}): CONFIG_WHITELIST_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config) -> bool:
    """Set up the Synology component."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    verify_ssl = conf.get(CONF_VERIFY_SSL)
    timeout = conf.get(CONF_TIMEOUT)

    try:
        surveillance = await hass.async_add_executor_job(
            partial(
                SurveillanceStation,
                config.get(CONF_URL),
                config.get(CONF_USERNAME),
                config.get(CONF_PASSWORD),
                verify_ssl=verify_ssl,
                timeout=timeout,
            )
        )
    except (requests.exceptions.RequestException, ValueError):
        _LOGGER.exception("Error when initializing SurveillanceStation")
        return False

    hass.data[DOMAIN_DATA] = {}
    # shared data
    hass.data[DOMAIN_DATA][DATA_SURVEILLANCE_CLIENT] = surveillance
    hass.data[DOMAIN_DATA][DATA_NAME] = conf.get(CONF_NAME)
    hass.data[DOMAIN_DATA][DATA_VERIFY_SSL] = verify_ssl

    return True
