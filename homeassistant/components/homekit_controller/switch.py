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

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        # pylint: disable=import-error
        from homekit.model.characteristics import CharacteristicsTypes
        return [
            CharacteristicsTypes.ON,
            CharacteristicsTypes.OUTLET_IN_USE,
        ]

    def _update_on(self, value):
        self._on = value

    def _update_outlet_in_use(self, value):
        self._outlet_in_use = value

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
    def device_state_attributes(self):
        """Return the optional state attributes."""
        if self._outlet_in_use is not None:
            return {
                OUTLET_IN_USE: self._outlet_in_use,
            }
