"""
Support for Rflink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rflink/
"""
import logging

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from . import (
    CONF_ALIASES, CONF_ALIASSES, CONF_DEVICE_DEFAULTS, CONF_DEVICES,
    CONF_FIRE_EVENT, CONF_GROUP, CONF_GROUP_ALIASES, CONF_GROUP_ALIASSES,
    CONF_NOGROUP_ALIASES, CONF_NOGROUP_ALIASSES, CONF_SIGNAL_REPETITIONS,
    DEVICE_DEFAULTS_SCHEMA, SwitchableRflinkDevice, remove_deprecated)

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE_DEFAULTS, default=DEVICE_DEFAULTS_SCHEMA({})):
        DEVICE_DEFAULTS_SCHEMA,
    vol.Optional(CONF_DEVICES, default={}): {
        cv.string: vol.Schema({
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
        })
    },
}, extra=vol.ALLOW_EXTRA)


def devices_from_config(domain_config):
    """Parse configuration and add Rflink switch devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device_config = dict(domain_config[CONF_DEVICE_DEFAULTS], **config)
        remove_deprecated(device_config)
        device = RflinkSwitch(device_id, **device_config)
        devices.append(device)

    return devices


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Rflink platform."""
    async_add_entities(devices_from_config(config))


# pylint: disable=too-many-ancestors
class RflinkSwitch(SwitchableRflinkDevice, SwitchDevice):
    """Representation of a Rflink switch."""

    pass
