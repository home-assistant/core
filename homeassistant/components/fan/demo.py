"""
Demo garage door platform that has a fake fan.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""

from homeassistant.components.fan import SPEED_LOW, SPEED_MED, SPEED_HIGH
from homeassistant.const import STATE_OFF
from homeassistant.helpers.entity import Entity


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup demo garage door platform."""
    add_devices_callback([
        DemoFan('Living Room Fan', SPEED_LOW),
    ])


class DemoFan(Entity):
    """A demonstration fan component."""

    def __init__(self, initial_state: str) -> None:
        """Initialize the entity."""
        self.speed = initial_state

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_MED, SPEED_HIGH]

    def turn_on(self, speed: str=SPEED_MED) -> None:
        """Turn on the entity."""
        self.set_speed(speed)

    def turn_off(self) -> None:
        """Turn off the entity."""
        self.speed = STATE_OFF
        self.oscillate(False)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self.speed = speed

    def ocillate(self, should_oscillate: bool) -> None:
        """Set oscillation."""
        self.is_oscillating = should_oscillate
