"""Support for Z-Wave fans."""
import logging
import math

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
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

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

# Value will first be divided to an integer
VALUE_TO_SPEED = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}
SPEED_TO_VALUE = {SPEED_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 50, SPEED_HIGH: 99}
SPEED_LIST = [*SPEED_TO_VALUE]


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

    def __init__(self, values):
        """Initialize the fan."""
        super().__init__(values)
        self._previous_speed = None

    async def async_set_speed(self, speed):
        """Set the speed of the fan."""
        if speed not in SPEED_TO_VALUE:
            _LOGGER.warning("Invalid speed received: %s", speed)
            return
        self._previous_speed = speed
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
        """Return the current speed.

        The Z-Wave speed value is a byte 0-255. 255 means previous value.
        The normal range of the speed is 0-99. 0 means off.
        """
        value = math.ceil(self.values.primary.value * 3 / 100)
        return VALUE_TO_SPEED.get(value, self._previous_speed)

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
