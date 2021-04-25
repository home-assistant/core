"""Component to embed TP-Link smart home devices."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .common import (
    ATTR_CONFIG,
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_STRIP,
    CONF_SWITCH,
    SmartDevices,
    async_discover_devices,
    get_static_devices,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "tplink"

TPLINK_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_LIGHT, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_SWITCH, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_STRIP, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_DIMMER, default=[]): vol.All(
                    cv.ensure_list, [TPLINK_HOST_SCHEMA]
                ),
                vol.Optional(CONF_DISCOVERY, default=True): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the TP-Link component."""
    conf = config.get(DOMAIN)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][ATTR_CONFIG] = conf

    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigType):
    """Set up TPLink from a config entry."""
    config_data = hass.data[DOMAIN].get(ATTR_CONFIG)

    # These will contain the initialized devices
    lights = hass.data[DOMAIN][CONF_LIGHT] = []
    switches = hass.data[DOMAIN][CONF_SWITCH] = []

    # Add static devices
    static_devices = SmartDevices()
    if config_data is not None:
        static_devices = get_static_devices(config_data)

        lights.extend(static_devices.lights)
        switches.extend(static_devices.switches)

    # Add discovered devices
    if config_data is None or config_data[CONF_DISCOVERY]:
        discovered_devices = await async_discover_devices(hass, static_devices)

        lights.extend(discovered_devices.lights)
        switches.extend(discovered_devices.switches)

    forward_setup = hass.config_entries.async_forward_entry_setup
    if lights:
        _LOGGER.debug(
            "Got %s lights: %s", len(lights), ", ".join([d.host for d in lights])
        )
        hass.async_create_task(forward_setup(config_entry, "light"))
    if switches:
        _LOGGER.debug(
            "Got %s switches: %s", len(switches), ", ".join([d.host for d in switches])
        )
        hass.async_create_task(forward_setup(config_entry, "switch"))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    forward_unload = hass.config_entries.async_forward_entry_unload
    remove_lights = remove_switches = False
    if hass.data[DOMAIN][CONF_LIGHT]:
        remove_lights = await forward_unload(entry, "light")
    if hass.data[DOMAIN][CONF_SWITCH]:
        remove_switches = await forward_unload(entry, "switch")

    if remove_lights or remove_switches:
        hass.data[DOMAIN].clear()
        return True

    # We were not able to unload the platforms, either because there
    # were none or one of the forward_unloads failed.
    return False
