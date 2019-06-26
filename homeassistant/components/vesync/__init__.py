"""Etekcity VeSync integration."""
import logging
import voluptuous as vol
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD, 
                                 CONF_TIME_ZONE, CONF_SCAN_INTERVAL)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.vesync import config_flow
from .common import async_process_devices, CONF_FANS, CONF_LIGHTS, CONF_SWITCHES
from .config_flow import configured_instances

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vesync'

DEFAULT_SCAN_INTERVAL = 36000

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIME_ZONE): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the VeSync component."""

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][CONF_SWITCHES] = []
    hass.data[DOMAIN][CONF_FANS] = []
    hass.data[DOMAIN][CONF_LIGHTS] = []

    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]

    if conf[CONF_USERNAME] not in configured_instances(hass):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                    CONF_TIME_ZONE: conf.get(CONF_TIME_ZONE)
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Vesync as config entry"""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    time_zone = None
    if config_entry.data[CONF_TIME_ZONE]:
        time_zone = config_entry.data[CONF_TIME_ZONE]
    else:
        if hass.config.time_zone is not None:
            time_zone = str(hass.config.time_zone)
            _LOGGER.debug("Time zone - %s", time_zone)

    from pyvesync import VeSync

    if time_zone is not None:

        manager = VeSync(username, password, time_zone)

    else:

        manager = VeSync(username, password)

    login = await hass.async_add_executor_job(manager.login)

    _LOGGER.debug("Login successful - %s", login)
    _LOGGER.debug(manager)

    if not login:
        _LOGGER.error("Unable to login")
        return False

    device_dict = await async_process_devices(hass, manager)

    hass.data[DOMAIN]['manager'] = manager

    forward_setup = hass.config_entries.async_forward_entry_setup

    lights = hass.data[DOMAIN][CONF_LIGHTS] = []
    switches = hass.data[DOMAIN][CONF_SWITCHES] = []
    fans = hass.data[DOMAIN][CONF_FANS] = []

    if device_dict[CONF_LIGHTS]:
        hass.async_create_task(forward_setup(config_entry, 'light'))
    if device_dict[CONF_SWITCHES]:
        hass.async_create_task(forward_setup(config_entry, 'switch'))
    if device_dict[CONF_FANS]:
        hass.async_create_task(forward_setup(config_entry, 'fan'))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHTS]:
        remove_lights = await forward_unload(entry, 'light')
    if hass.data[DOMAIN][CONF_SWITCHES]:
        remove_switches = await forward_unload(entry, 'switch')
    if hass.data[DOMAIN][CONF_FANS]:
        remove_switches = await forward_unload(entry, 'fan')

    if remove_lights or remove_switches:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False
