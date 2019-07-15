"""Etekcity VeSync integration."""
import logging
import voluptuous as vol
from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 CONF_TIME_ZONE)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.config_entries import SOURCE_IMPORT
from .common import (async_process_devices, CONF_SWITCHES)
from .config_flow import configured_instances
from .const import VS_DISPATCHERS, VS_DISCOVERY, SERVICE_UPDATE_DEVS, CONF_MANAGER

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vesync'

DEFAULT_SCAN_INTERVAL = 36000

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIME_ZONE): cv.time_zone,
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
                    CONF_TIME_ZONE: conf.get(CONF_TIME_ZONE)
                }))

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Vesync as config entry."""
    manager = config_entry.data[CONF_MANAGER]

    device_dict = await async_process_devices(hass, manager)

    hass.data[DOMAIN]['manager'] = manager

    forward_setup = hass.config_entries.async_forward_entry_setup

    switches = hass.data[DOMAIN][CONF_SWITCHES] = []

    hass.data[DOMAIN][VS_DISPATCHERS] = []

    if device_dict[CONF_SWITCHES]:
        switches.extend(device_dict[CONF_SWITCHES])
        hass.async_create_task(forward_setup(config_entry, 'switch'))

    async def async_new_device_discovery(service):
        """Discover if new devices should be added."""
        if hass.data[DOMAIN].get('manager') is None:
            _LOGGER.warning(
                'Cannot get new devices - VeSync manager not loaded')
            return

        manager = hass.data[DOMAIN]['manager']
        switches = hass.data[DOMAIN][CONF_SWITCHES]

        dev_dict = await async_process_devices(hass, manager)
        switch_devs = dev_dict.get(CONF_SWITCHES, [])

        if switch_devs:
            switch_set = set(switch_devs)
            new_switches = list(switch_set.difference(switches))
            switch_len = len(new_switches)
            switches.extend(new_switches)
            async_dispatcher_send(hass, VS_DISCOVERY.format(CONF_SWITCHES),
                                  switch_len)

    hass.services.async_register(DOMAIN,
                                 SERVICE_UPDATE_DEVS,
                                 async_new_device_discovery
                                 )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_switches = False
    if hass.data[DOMAIN][CONF_SWITCHES]:
        remove_switches = await forward_unload(entry, 'switch')

    if remove_switches:
        hass.services.async_remove(DOMAIN, SERVICE_UPDATE_DEVS)
        del hass.data[DOMAIN]
        return True

    return False
