"""
Support for Eneco Slimmer stekkers (Smart Plugs).

This provides controlls for the z-wave smart plugs Toon can control.
"""
import logging

from homeassistant.components.switch import SwitchDevice
import homeassistant.components.toon as toon_main

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup discovered Smart Plugs."""
    _toon_main = hass.data[toon_main.TOON_HANDLE]
    switch_items = []
    for plug in _toon_main.toon.smartplugs:
        switch_items.append(EnecoSmartPlug(hass, plug))

    add_devices_callback(switch_items)


class EnecoSmartPlug(SwitchDevice):
    """Representation of a Smart Plug."""

    def __init__(self, hass, plug):
        """Initialize the Smart Plug."""
        self.smartplug = plug
        self.toon_data_store = hass.data[toon_main.TOON_HANDLE]

    @property
    def should_poll(self):
        """No polling needed with subscriptions."""
        return True

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
        """Current power usage in W."""
        return self.toon_data_store.get_data('current_power', self.name)

    @property
    def today_energy_kwh(self):
        """Today total energy usage in kWh."""
        return self.toon_data_store.get_data('today_energy', self.name)

    @property
    def is_on(self):
        """Return true if switch is on. Standby is on."""
        return self.toon_data_store.get_data('current_state', self.name)

    @property
    def available(self):
        """True if switch is available."""
        return self.smartplug.can_toggle

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        return self.smartplug.turn_on()

    def turn_off(self):
        """Turn the switch off."""
        return self.smartplug.turn_off()

    def update(self):
        """Update state."""
        self.toon_data_store.update()
