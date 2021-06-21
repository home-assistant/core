"""Support for Lutron fans."""

from homeassistant.components.fan import (
    DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice, DOMAIN as LUTRON_DOMAIN

FAN_OFF, FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH = 0, 25, 50, 75, 100

DEFAULT_ON_PERCENTAGE = 50
ORDERED_NAMED_FAN_SPEEDS = [FAN_LOW, FAN_MEDIUM, FAN_MEDIUM_HIGH, FAN_HIGH]

def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up the Lutron fans."""
    devs = []

    # Add Lutron Fans
    for (area_name, device) in hass.data[LUTRON_DEVICES][DOMAIN]:
        dev = LutronFan(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)

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
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def supported_features(self) -> int:
        """Flag supported features. Speed Only."""
        return SUPPORT_SET_SPEED

    @property
    def percentage(self) -> int:
        """Return the current speed percentage. Must be a value between 0 (off) and 100"""
        return self._lutron_device.last_level()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._lutron_device.last_level() > 0

    def turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs
    ) -> None:
        """Turn the fan on."""
        if percentage is None:
            percentage = DEFAULT_ON_PERCENTAGE

        self.set_percentage(percentage)

    def turn_off(self, **kwargs) -> None:
        """Turn the fan off."""
        self.set_percentage(0)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""

        if percentage == 0:
            named_speed = FAN_OFF
        else:
            named_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )

        self._lutron_device.level = percentage
