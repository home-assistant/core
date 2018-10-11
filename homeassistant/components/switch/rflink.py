"""
Support for Rflink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rflink/
"""
import logging

from homeassistant.components.rflink import (
    CONF_ALIASES, CONF_ALIASSES, CONF_DEVICE_DEFAULTS, CONF_DEVICES,
    CONF_FIRE_EVENT, CONF_GROUP, CONF_GROUP_ALIASES, CONF_GROUP_ALIASSES,
    CONF_NOGROUP_ALIASES, CONF_NOGROUP_ALIASSES, CONF_SIGNAL_REPETITIONS,
    DEVICE_DEFAULTS_SCHEMA, DOMAIN, SwitchableRflinkDevice, cv,
    remove_deprecated, vol)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME, CONF_PLATFORM

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
    DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_NOGROUP_ALIASES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_FIRE_EVENT): cv.boolean,
            vol.Optional(CONF_SIGNAL_REPETITIONS): vol.Coerce(int),
            vol.Optional(CONF_GROUP, default=True): cv.boolean,
            # deprecated config options
            vol.Optional(CONF_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_GROUP_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(CONF_NOGROUP_ALIASSES):
                vol.All(cv.ensure_list, [cv.string]),
        },
    }),
})


def devices_from_config(domain_config, hass=None):
    """Parse configuration and add Rflink switch devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)
        remove_deprecated(device_config)
        device = RflinkSwitch(device_id, hass, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config, hass))


class RflinkSwitch(SwitchableRflinkDevice, SwitchDevice):
    """Representation of a Rflink switch."""

    pass
