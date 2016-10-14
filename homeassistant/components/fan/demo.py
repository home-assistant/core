"""
Demo fan platform that has a fake fan.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""

from homeassistant.components.fan import (SPEED_LOW, SPEED_MED, SPEED_HIGH,
                                          FanEntity, SUPPORT_SET_SPEED,
                                          SUPPORT_OSCILLATE)
from homeassistant.const import STATE_OFF


FAN_NAME = 'Living Room Fan'
FAN_ENTITY_ID = 'fan.living_room_fan'

DEMO_SUPPORT = SUPPORT_SET_SPEED | SUPPORT_OSCILLATE


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup demo fan platform."""
    add_devices_callback([
        DemoFan(hass, FAN_NAME, STATE_OFF),
    ])


class DemoFan(FanEntity):
    """A demonstration fan component."""

    def __init__(self, hass, name: str, initial_state: str) -> None:
        """Initialize the entity."""
        self.hass = hass
        self.speed = initial_state
        self.oscillating = False
        self._name = name

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo fan."""
        return False

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_MED, SPEED_HIGH]

    def turn_on(self, speed: str=SPEED_MED) -> None:
        """Turn on the entity."""
        self.set_speed(speed)

    def turn_off(self) -> None:
        """Turn off the entity."""
        self.oscillate(False)
        self.set_speed(STATE_OFF)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        self.speed = speed
        self.update_ha_state()

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self.oscillating = oscillating
        self.update_ha_state()

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return DEMO_SUPPORT
