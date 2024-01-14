"""TOD."""

from homeassistant.components.switch import SwitchEntity


class MySwitch(SwitchEntity):
    """TOD."""

    _attr_has_entity_name = True

    def __init__(self):
        """TOD."""
        self._is_on = False
        self._attr_device_info = ...  # For automatic device registration
        self._attr_unique_id = ...

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
