"""
Support for LiteJet switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.litejet/
"""
import logging

from homeassistant.components import litejet
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['litejet']

ATTR_NUMBER = 'number'

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the LiteJet switch platform."""
    litejet_ = hass.data['litejet_system']

    devices = []
    for i in litejet_.button_switches():
        name = litejet_.get_switch_name(i)
        if not litejet.is_ignored(hass, name):
            devices.append(LiteJetSwitch(hass, litejet_, i, name))
    add_entities(devices, True)


class LiteJetSwitch(SwitchDevice):
    """Representation of a single LiteJet switch."""

    def __init__(self, hass, lj, i, name):
        """Initialize a LiteJet switch."""
        self._hass = hass
        self._lj = lj
        self._index = i
        self._state = False
        self._name = name

        lj.on_switch_pressed(i, self._on_switch_pressed)
        lj.on_switch_released(i, self._on_switch_released)

    def _on_switch_pressed(self):
        _LOGGER.debug("Updating pressed for %s", self._name)
        self._state = True
        self.schedule_update_ha_state()

    def _on_switch_released(self):
        _LOGGER.debug("Updating released for %s", self._name)
        self._state = False
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return if the switch is pressed."""
        return self._state

    @property
    def should_poll(self):
        """Return that polling is not necessary."""
        return False

    @property
    def device_state_attributes(self):
        """Return the device-specific state attributes."""
        return {
            ATTR_NUMBER: self._index
        }

    def turn_on(self, **kwargs):
        """Press the switch."""
        self._lj.press_switch(self._index)

    def turn_off(self, **kwargs):
        """Release the switch."""
        self._lj.release_switch(self._index)
