"""Support for Z-Wave fans."""
import math

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

SPEED_LIST = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

# Value will first be divided to an integer
VALUE_TO_SPEED = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}

SPEED_TO_VALUE = {SPEED_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 50, SPEED_HIGH: 99}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Fan from Config Entry."""

    @callback
    def async_add_fan(values):
        """Add Z-Wave Fan."""
        fan = ZwaveFan(values)
        async_add_entities([fan])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, "zwave_new_fan", async_add_fan)
    )

    await hass.data[DOMAIN][config_entry.entry_id]["mark_platform_loaded"]("fan")


class ZwaveFan(ZWaveDeviceEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    async def async_set_speed(self, speed):
        """Set the speed of the fan."""
        self.values.primary.send_value(SPEED_TO_VALUE[speed])

    async def async_turn_on(self, speed=None, **kwargs):
        """Turn the device on."""
        if speed is None:
            # Value 255 tells device to return to previous value
            self.values.primary.send_value(255)
        else:
            await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self.values.primary.send_value(0)

    @property
    def is_on(self):
        """Return true if device is on (speed above 0)."""
        return self.values.primary.value > 0

    @property
    def speed(self):
        """Return the current speed."""
        value = math.ceil(self.values.primary.value * 3 / 100)
        return VALUE_TO_SPEED[value]

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
