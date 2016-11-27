"""
Support for Rflink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rflink/
"""
import asyncio
import logging

import homeassistant.components.rflink as rflink
from homeassistant.components.switch import SwitchDevice

from . import DOMAIN

DEPENDENCIES = ['rflink']

_LOGGER = logging.getLogger(__name__)

VALID_CONFIG_KEYS = [
    'aliasses',
    'name',
    'icon',
]


def devices_from_config(domain_config, hass=None):
    """Parse config and add rflink switch devices."""

    devices = []
    for device_id, config in domain_config['devices'].items():
        # extract only valid keys from device configuration
        kwargs = {k: v for k, v in config.items() if k in VALID_CONFIG_KEYS}
        devices.append(RflinkSwitch(device_id, hass, **kwargs))
    return devices


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the Rflink platform."""
    yield from async_add_devices(devices_from_config(config, hass))


class RflinkSwitch(rflink.SwitchableRflinkDevice, SwitchDevice):
    """Representation of a Rflink switch."""

    # used for matching bus events
    domain = DOMAIN

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon
