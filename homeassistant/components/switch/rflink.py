"""Support for Rflink switches.

For more details about this platform, please refer to the documentation
at https://home-assistant.io/components/switch.rflink/

"""
import asyncio
import logging

from homeassistant.components.rflink import (
    CONF_ALIASSES, CONF_DEVICES, DATA_ENTITY_LOOKUP, DATA_KNOWN_DEVICES,
    DOMAIN, EVENT_KEY_COMMAND, SwitchableRflinkDevice, cv, vol)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_NAME, CONF_PLATFORM

from . import DOMAIN as PLATFORM

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): DOMAIN,
    vol.Optional(CONF_DEVICES, default={}): vol.Schema({
        cv.string: {
            vol.Optional(CONF_NAME): cv.string,
            vol.Optional(CONF_ALIASSES, default=[]):
                vol.All(cv.ensure_list, [cv.string]),
        },
    }),
})


def devices_from_config(domain_config, hass=None):
    """Parse config and add rflink switch devices."""
    devices = []
    for device_id, config in domain_config[CONF_DEVICES].items():
        device = RflinkSwitch(device_id, hass, **config)
        devices.append(device)
        hass.data[DATA_KNOWN_DEVICES].append(device_id)
        # register entity (and aliasses) to listen to incoming rflink events
        for _id in config[CONF_ALIASSES] + [device_id]:
            hass.data[DATA_ENTITY_LOOKUP][
                EVENT_KEY_COMMAND][_id].append(device)
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    yield from async_add_devices(devices_from_config(config, hass))


class RflinkSwitch(SwitchableRflinkDevice, SwitchDevice):
    """Representation of a Rflink switch."""

    # used for matching bus events
    platform = PLATFORM
