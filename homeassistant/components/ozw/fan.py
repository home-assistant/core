"""Support for Z-Wave fans."""
import math

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

SUPPORTED_FEATURES = SUPPORT_SET_SPEED
SPEED_RANGE = (1, 99)  # off is not included


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Fan from Config Entry."""

    @callback
    def async_add_fan(values):
        """Add Z-Wave Fan."""
        fan = ZwaveFan(values)
        async_add_entities([fan])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{FAN_DOMAIN}", async_add_fan)
    )


class ZwaveFan(ZWaveDeviceEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    async def async_set_percentage(self, percentage):
        """Set the speed percentage of the fan."""
        if percentage is None:
            # Value 255 tells device to return to previous value
            zwave_speed = 255
        elif percentage == 0:
            zwave_speed = 0
        else:
            zwave_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        self.values.primary.send_value(zwave_speed)

    async def async_turn_on(
        self, speed=None, percentage=None, preset_mode=None, **kwargs
    ):
        """Turn the device on."""
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self.values.primary.send_value(0)

    @property
    def is_on(self):
        """Return true if device is on (speed above 0)."""
        return self.values.primary.value > 0

    @property
    def percentage(self):
        """Return the current speed.

        The Z-Wave speed value is a byte 0-255. 255 means previous value.
        The normal range of the speed is 0-99. 0 means off.
        """
        return ranged_value_to_percentage(SPEED_RANGE, self.values.primary.value)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
