"""Component to embed TP-Link smart home devices."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import (
    async_discover_devices,
    async_get_static_devices,
    async_has_discoverable_devices,
    ATTR_CONFIG,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_SWITCH,
    SmartDevices
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'tplink'

TPLINK_HOST_SCHEMA = vol.Schema({
    vol.Required(CONF_HOST): cv.string
})


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional('light', default=[]): vol.All(cv.ensure_list,
                                                   [TPLINK_HOST_SCHEMA]),
        vol.Optional('switch', default=[]): vol.All(cv.ensure_list,
                                                    [TPLINK_HOST_SCHEMA]),
        vol.Optional('discovery', default=True): cv.boolean,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={'source': config_entries.SOURCE_IMPORT}))

    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigType):
    """Set up TPLink from a config entry."""
    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHT] = []
    switches = hass.data[DOMAIN][CONF_SWITCH] = []

    # Add static devices
    static_devices = SmartDevices()
    if config_data is not None:
        static_devices = async_get_static_devices(
            config_data,
        )

        for light in static_devices.lights:
            lights.append(light)

        for switch in static_devices.switches:
            switches.append(switch)

    # Add discovered devices
    if config_data is None or config_data[CONF_DISCOVERY]:
        discovered_devices = await async_discover_devices(hass)

        for light in discovered_devices.lights:
            if not static_devices.has_device_with_host(light.host):
                lights.append(light)

        for switch in discovered_devices.switches:
            if not static_devices.has_device_with_host(switch.host):
                switches.append(switch)

    forward_setup = hass.config_entries.async_forward_entry_setup
    if lights:
        _LOGGER.debug("Got %s lights: %s", len(lights), lights)
        hass.async_create_task(forward_setup(config_entry, 'light'))
    if switches:
        _LOGGER.debug("Got %s switches: %s", len(switches), switches)
        hass.async_create_task(forward_setup(config_entry, 'switch'))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHT]:
        remove_lights = await forward_unload(entry, 'light')
    if hass.data[DOMAIN][CONF_SWITCH]:
        remove_switches = await forward_unload(entry, 'switch')

    if remove_lights or remove_switches:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False


config_entry_flow.register_discovery_flow(DOMAIN,
                                          'TP-Link Smart Home',
                                          async_has_discoverable_devices,
                                          config_entries.CONN_CLASS_LOCAL_POLL)
