"""Etekcity VeSync integration."""
import logging
import voluptuous as vol
from itertools import chain
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_TIME_ZONE)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.config_entries import SOURCE_IMPORT
from .common import (async_process_devices, CONF_FANS,
                     CONF_LIGHTS, CONF_SWITCHES)
from .config_flow import configured_instances
from .const import VS_DISPATCHERS, VS_DISCOVERY, SERVICE_UPDATE_DEVS

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

    conf = config.get('vesync')

    if isinstance(conf, dict) and\
            conf[CONF_USERNAME] in configured_instances(hass):
        return True

    if isinstance(conf, dict) and\
            conf[CONF_USERNAME] not in configured_instances(hass):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={'source': SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                    CONF_TIME_ZONE: conf.get(CONF_TIME_ZONE, None)
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]
    time_zone = config_entry.data[CONF_TIME_ZONE]

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

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    device_dict = await async_process_devices(hass, manager)

    hass.data[DOMAIN]['manager'] = manager

    forward_setup = hass.config_entries.async_forward_entry_setup

    lights = hass.data[DOMAIN][CONF_LIGHTS] = []
    switches = hass.data[DOMAIN][CONF_SWITCHES] = []
    fans = hass.data[DOMAIN][CONF_FANS] = []

    hass.data[DOMAIN][VS_DISPATCHERS] = []

    if device_dict[CONF_LIGHTS]:
        lights.extend(device_dict[CONF_LIGHTS])
        hass.async_create_task(forward_setup(config_entry, 'light'))
    if device_dict[CONF_SWITCHES]:
        switches.extend(device_dict[CONF_SWITCHES])
        hass.async_create_task(forward_setup(config_entry, 'switch'))
    if device_dict[CONF_FANS]:
        fans.extend(device_dict[CONF_FANS])
        hass.async_create_task(forward_setup(config_entry, 'fan'))
    _LOGGER.debug(str(lights))

    async def async_new_device_discovery(hass):
        """Discover if new devices should be added."""
        if hass[DOMAIN].get('manager') is None:
            _LOGGER.warning('Cannot get new devices - VeSync manager not loaded')
            return

        manager = hass[DOMAIN]['manager']
        lights = hass[DOMAIN][CONF_LIGHTS]
        fans = hass[DOMAIN][CONF_FANS]
        switches = hass[DOMAIN][CONF_SWITCHES]

        dev_dict = await async_process_devices(hass, manager)
        fan_devs = dev_dict.get(CONF_FANS, [])
        light_devs = dev_dict.get(CONF_LIGHTS, [])
        switch_devs = dev_dict.get(CONF_SWITCHES, [])

        if fan_devs:
            fan_set = set(fan_devs)
            new_fans = list(fan_set.difference(fans))
            fan_len = len(new_fans)
            fans.extend(new_fans)
            async_dispatcher_send(hass, VS_DISCOVERY.format(CONF_FANS),
                                  fans[-fan_len:])

        if light_devs:
            light_set = set(light_devs)
            new_lights = list(light_set.difference(lights))
            light_len = len(new_lights)
            lights.extend(new_lights)
            async_dispatcher_send(hass, VS_DISCOVERY.format(CONF_LIGHTS),
                                  lights[-light_len:])

        if switch_devs:
            switch_set = set(switch_devs)
            new_switches = list(switch_set.difference(switches))
            switch_len = len(new_switches)
            switches.extend(new_switches)
            async_dispatcher_send(hass, VS_DISCOVERY.format(CONF_SWITCHES),
                                  switches[-switch_len:])

    hass.services.async_register(DOMAIN,
                                 SERVICE_UPDATE_DEVS,
                                 async_new_device_discovery
                                 )

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
        remove_fans = await forward_unload(entry, 'fan')

    if remove_lights or remove_switches or remove_fans:
        hass.data[DOMAIN].clear()
        return True

    return False
