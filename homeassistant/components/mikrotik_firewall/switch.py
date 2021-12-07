"""Mikrotik firewall rule switch."""

from homeassistant.components.switch import SwitchEntity


class RuleSwitch(SwitchEntity):
    """Firewall rule switch."""

    def __init__(self):
        """Class setup."""
        self._is_on = False

    @property
    def name(self):
        """Name of the entity."""
        return "My Switch"

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._is_on = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._is_on = False
