"""Support for the myLeviton decora_wifi component."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .common import DecoraWifiCommFailed, DecoraWifiPlatform, DecoraWifiSessionNotFound
from .const import CONF_OPTIONS, DEFAULT_SCAN_INTERVAL, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DECORAWIFI_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {
            DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_SCAN_INTERVAL, default=120): cv.positive_int,
                },
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Decora Wifi component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    # Trigger import config flow
    conf = config[DOMAIN]

    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                },
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry):
    """Set up Decora Wifi from a config entry."""

    conf_data = dict(entry.data)
    email = conf_data[CONF_USERNAME]
    password = conf_data[CONF_PASSWORD]

    conf_data[CONF_OPTIONS] = {}
    # If no scan interval option was set in the config entry, use the default.
    conf_data[CONF_OPTIONS].update(
        {
            CONF_SCAN_INTERVAL: dict(entry.options).get(
                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
            )
        }
    )
    hass.data[DOMAIN][entry.entry_id] = email
    devices = {}

    try:
        devices = await DecoraWifiPlatform.async_getdevices(hass, email)
    except DecoraWifiCommFailed:
        _LOGGER.error("Communication with Decora Wifi platform failed.")
        return False
    except DecoraWifiSessionNotFound:
        # Re-login.
        if await DecoraWifiPlatform.async_login(hass, email, password):
            devices = await DecoraWifiPlatform.async_getdevices(hass, email)

    # Forward the config entry for each device type present.
    for p in PLATFORMS:
        if devices[p]:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, p)
            )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    conf_data = dict(entry.data)
    email = conf_data[CONF_USERNAME]
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await DecoraWifiPlatform.async_logout(hass, email)
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
