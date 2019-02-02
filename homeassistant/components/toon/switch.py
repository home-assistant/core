"""
Support for Eneco Slimmer stekkers (Smart Plugs).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.toon/
"""
import logging

from homeassistant.components.switch import SwitchDevice
import homeassistant.components.toon as toon_main

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the discovered Toon Smart Plugs."""
    _toon_main = hass.data[toon_main.TOON_HANDLE]
    switch_items = []
    for plug in _toon_main.toon.smartplugs:
        switch_items.append(EnecoSmartPlug(hass, plug))

    add_entities(switch_items)


class EnecoSmartPlug(SwitchDevice):
    """Representation of a Toon Smart Plug."""

    def __init__(self, hass, plug):
        """Initialize the Smart Plug."""
        self.smartplug = plug
        self.toon_data_store = hass.data[toon_main.TOON_HANDLE]

    @property
    def unique_id(self):
        """Return the ID of this switch."""
        return self.smartplug.device_uuid

    @property
    def name(self):
        """Return the name of the switch if any."""
        return self.smartplug.name

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.toon_data_store.get_data('current_power', self.name)

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        return self.toon_data_store.get_data('today_energy', self.name)

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self.toon_data_store.get_data('current_state', self.name)

    @property
    def available(self):
        """Return true if switch is available."""
        return self.smartplug.can_toggle

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        return self.smartplug.turn_on()

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        return self.smartplug.turn_off()

    def update(self):
        """Update state."""
        self.toon_data_store.update()
