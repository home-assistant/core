"""
Demo fan platform that has a fake fan.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
                                          FanEntity, SUPPORT_SET_SPEED,
                                          SUPPORT_OSCILLATE, SUPPORT_DIRECTION)
from homeassistant.const import STATE_OFF

FULL_SUPPORT = SUPPORT_SET_SPEED | SUPPORT_OSCILLATE | SUPPORT_DIRECTION
LIMITED_SUPPORT = SUPPORT_SET_SPEED


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the demo fan platform."""
    add_devices_callback([
        DemoFan(hass, "Living Room Fan", FULL_SUPPORT),
        DemoFan(hass, "Ceiling Fan", LIMITED_SUPPORT),
    ])


class DemoFan(FanEntity):
    """A demonstration fan component."""

    def __init__(self, hass, name: str, supported_features: int) -> None:
        """Initialize the entity."""
        self.hass = hass
        self._supported_features = supported_features
        self._speed = STATE_OFF
        self._speed_pct = 0
        self.oscillating = None
        self.direction = None
        self._name = name

        if supported_features & SUPPORT_OSCILLATE:
            self.oscillating = False
        if supported_features & SUPPORT_DIRECTION:
            self.direction = "forward"

    @property
    def name(self) -> str:
        """Get entity name."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed for a demo fan."""
        return False

    @property
    def speed(self) -> str:
        """Return the current speed."""
        return self._speed

    @property
    def speed_pct(self) -> int:
        """Return the current speed in percent between 0..100."""
        return self._speed_pct

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed: str = None, speed_pct: int = None,
                **kwargs) -> None:
        """Turn on the entity."""
        if speed is None and speed_pct is None:
            speed = SPEED_MEDIUM
        self.set_speed(speed, None)

    def turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        self.oscillate(False)
        self.set_speed(STATE_OFF)

    def set_speed(self, speed: str = None, speed_pct: int = None) -> None:
        """Set the speed of the fan."""
        if speed is not None:
            if speed == STATE_OFF:
                speed_pct = 0
            elif speed == SPEED_LOW:
                speed_pct = 30
            elif speed == SPEED_MEDIUM:
                speed_pct = 60
            elif speed == SPEED_HIGH:
                speed_pct = 100
        elif speed_pct is not None:
            if speed_pct == 0:
                speed = STATE_OFF
            elif speed_pct <= 30:
                speed = SPEED_LOW
            elif speed_pct <= 60:
                speed = SPEED_MEDIUM
            elif speed <= 100:
                speed = SPEED_HIGH
        self._speed = speed
        self._speed_pct = speed_pct
        self.schedule_update_ha_state()

    def set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        self.direction = direction
        self.schedule_update_ha_state()

    def oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        self.oscillating = oscillating
        self.schedule_update_ha_state()

    @property
    def current_direction(self) -> str:
        """Fan direction."""
        return self.direction

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features
