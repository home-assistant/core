import logging

from homeassistant.components.switch import SwitchEntity

# Create a logger
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Domintell switch platform."""
    # This function is executed when Home Assistant loads your switch platform.
    # This is where you'd normally process any discovered devices.
    # For now, we're just going to create a single virtual switch entity.

    if discovery_info is None:
        return

    switch_name = discovery_info
    _LOGGER.info(f"Setting up Domintell virtual switch: {switch_name}")

    switch_entity = DomintellVirtualSwitch(switch_name)
    add_entities([switch_entity])


class DomintellVirtualSwitch(SwitchEntity):
    """Representation of a Domintell virtual switch."""

    def __init__(self, name):
        """Initialize the switch."""
        self._name = name
        self._unique_id = f"domintell_{name.lower().replace(' ', '_')}"
        self._state = False

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        _LOGGER.info(f"Unique ID: {self._unique_id}")
        return self._unique_id

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return True if the switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        # In a real implementation, you'd have logic here to turn on the actual device.
        _LOGGER.info("Domintell switch turned ON")
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        # In a real implementation, you'd have logic here to turn off the actual device.
        _LOGGER.info("Domintell switch turned  OFF")
        self._state = False
        self.async_write_ha_state()
