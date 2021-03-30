"""Support for Z-Wave fans."""
import math

from homeassistant.components.fan import DOMAIN, SUPPORT_SET_SPEED, FanEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import ZWaveDeviceEntity

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

SPEED_RANGE = (1, 99)  # off is not included


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Fan from Config Entry."""

    @callback
    def async_add_fan(fan):
        """Add Z-Wave Fan."""
        async_add_entities([fan])

    async_dispatcher_connect(hass, "zwave_new_fan", async_add_fan)


def get_device(values, **kwargs):
    """Create Z-Wave entity device."""
    return ZwaveFan(values)


class ZwaveFan(ZWaveDeviceEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    def __init__(self, values):
        """Initialize the Z-Wave fan device."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self.update_properties()

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self.values.primary.data

    def set_percentage(self, percentage):
        """Set the speed percentage of the fan."""
        if percentage is None:
            # Value 255 tells device to return to previous value
            zwave_speed = 255
        elif percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        self.node.set_dimmer(self.values.primary.value_id, zwave_speed)

    def turn_on(self, speed=None, percentage=None, preset_mode=None, **kwargs):
        """Turn the device on."""
        self.set_percentage(percentage)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.node.set_dimmer(self.values.primary.value_id, 0)

    @property
    def percentage(self):
        """Return the current speed percentage."""
        return ranged_value_to_percentage(SPEED_RANGE, self._state)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
