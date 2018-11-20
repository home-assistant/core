"""
Support for Volvo heater.

This platform uses the Volvo online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.volvooncall/
"""
import logging

from homeassistant.components.volvooncall import VolvoEntity, RESOURCES
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a Volvo switch."""
    if discovery_info is None:
        return
    add_entities([VolvoSwitch(hass, *discovery_info)])


class VolvoSwitch(VolvoEntity, ToggleEntity):
    """Representation of a Volvo switch."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.vehicle.is_heater_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.vehicle.start_heater()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self.vehicle.stop_heater()

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]
