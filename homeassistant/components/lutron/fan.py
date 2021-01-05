"""Support for Lutron fans."""
from typing import Optional
from bisect import bisect_left

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

# This currently omits the Medium-High setting of 75%.
FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_HIGH = 0, 25, 50, 100

VALUE_TO_SPEED = {
    None: SPEED_OFF,
    FAN_OFF: SPEED_OFF,
    FAN_LOW: SPEED_LOW,
    FAN_MEDIUM: SPEED_MEDIUM,
    FAN_HIGH: SPEED_HIGH,
}

SPEED_TO_VALUE = {
    SPEED_OFF: FAN_OFF,
    SPEED_LOW: FAN_LOW,
    SPEED_MEDIUM: FAN_MEDIUM,
    SPEED_HIGH: FAN_HIGH,
}

FAN_SPEEDS = list(SPEED_TO_VALUE.keys())


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Lutron fans."""
    devs = []

    # Add Lutron Fans
    for (area_name, device) in hass.data[LUTRON_DEVICES]["fan"]:
        dev = LutronFan(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)


def to_lutron_speed(speed: str) -> int:
    """Convert the given Home Assistant fan speed (off, low, medium, high) to Lutron (0-100)."""
    return SPEED_TO_VALUE[speed]


def to_hass_speed(speed: float) -> str:
    """Convert the given Lutron (0.0-100.0) light level to Home Assistant (0-255)."""
    discrete_speeds = list(VALUE_TO_SPEED.keys())
    discrete_speeds.remove(None)
    idx = bisect_left(discrete_speeds, speed)

    return VALUE_TO_SPEED[discrete_speeds[idx]]


class LutronFan(LutronDevice, FanEntity):
    """Representation of a Lutron Fan controller. Including Fan Speed."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the fan device."""
        self._prev_speed = None
        super().__init__(area_name, lutron_device, controller)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"lutron_integration_id": self._lutron_device.id}

    @property
    def supported_features(self) -> int:
        """Flag supported features. Speed Only."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self) -> Optional[str]:
        """Return the speed of the fan."""
        new_speed = to_hass_speed(self._lutron_device.last_level())
        if new_speed != SPEED_OFF:
            self._prev_speed = new_speed
        return new_speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return FAN_SPEEDS

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn the fan on."""
        if speed is not None:
            new_speed = speed
        elif not self._prev_speed:
            new_speed = SPEED_MEDIUM
        else:
            new_speed = self._prev_speed

        self.set_speed(new_speed)

    def turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        self.set_speed(SPEED_OFF)

    def set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed is not SPEED_OFF:
            self._prev_speed = speed
        self._lutron_device.level = to_lutron_speed(speed)
