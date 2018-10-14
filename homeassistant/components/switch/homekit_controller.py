"""
Support for Homekit switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.homekit_controller/
"""
import logging

from homeassistant.components.homekit_controller import (HomeKitEntity,
                                                         KNOWN_ACCESSORIES)
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['homekit_controller']

OUTLET_IN_USE = "outlet_in_use"

PROP_TO_ATTR = {
    'outlet_in_use': OUTLET_IN_USE
}

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Homekit switch support."""
    if discovery_info is not None:
        accessory = hass.data[KNOWN_ACCESSORIES][discovery_info['serial']]
        add_entities([HomeKitSwitch(accessory, discovery_info)], True)


class HomeKitSwitch(HomeKitEntity, SwitchDevice):
    """Representation of a Homekit switch."""

    def __init__(self, *args):
        """Initialise the switch."""
        super().__init__(*args)
        self._on = None
        self._outlet_in_use = None

    def update_characteristics(self, characteristics):
        """Synchronise the switch state with Home Assistant."""
        import homekit  # pylint: disable=import-error

        for characteristic in characteristics:
            ctype = characteristic['type']
            ctype = homekit.CharacteristicsTypes.get_short(ctype)
            if ctype == "on":
                self._chars['on'] = characteristic['iid']
                self._on = characteristic['value']
            elif ctype == "outlet-in-use":
                self._chars['outlet-in-use'] = characteristic['iid']
                self._outlet_in_use = characteristic['value']

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._on

    def turn_on(self, **kwargs):
        """Turn the specified switch on."""
        self._on = True
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['on'],
                            'value': True}]
        self.put_characteristics(characteristics)

    def turn_off(self, **kwargs):
        """Turn the specified switch off."""
        characteristics = [{'aid': self._aid,
                            'iid': self._chars['on'],
                            'value': False}]
        self.put_characteristics(characteristics)

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {}

        for prop, attr in PROP_TO_ATTR.items():
            value = getattr(self, prop)
            if value is not None:
                data[attr] = value

        return data

    @property
    def outlet_in_use(self):
        """Return true if device is plugged to outlet."""
        return self._outlet_in_use
