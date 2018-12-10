"""
Z-Wave platform that handles fans.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.zwave/
"""
import logging

from homeassistant.core import callback
from homeassistant.components.fan import (
    DOMAIN, FanEntity, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED)
from homeassistant.components import zwave
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

HOMESEER_FC200 = (0x000c, 0x0001)

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Old method of setting up Z-Wave fans."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Fan from Config Entry."""
    @callback
    def async_add_fan(fan):
        """Add Z-Wave Fan."""
        async_add_entities([fan])

    async_dispatcher_connect(hass, 'zwave_new_fan', async_add_fan)


def get_device(node, values, node_config, **kwargs):
    """Create Z-Wave entity device."""
    return ZwaveFan(values)

class ZwaveFan(zwave.ZWaveDeviceEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    def __init__(self, values):
        """Initialize the Z-Wave fan device."""
        zwave.ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._init_speed_value_mappings()
        self.update_properties()

    def _init_speed_value_mappings(self):
        """Build maps to translate between logical speeds and dimmer values."""
        if self._device_id() == HOMESEER_FC200:
            self._speed_list = [SPEED_OFF, "1", "2", "3", "4"]
            self._speed_to_values = {
                SPEED_OFF: [0],
                "1": range(1, 25),
                "2": range(25, 50),
                "3": range(50, 75),
                "4": range(75, 101)
        }
        else:
            self._speed_list = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
            self._speed_to_values = {
                SPEED_OFF: [0],
                SPEED_LOW: range(1, 34),
                SPEED_MEDIUM: range(34, 67),
                SPEED_HIGH: range(67, 101)
            }

        self._value_to_speed = {}
        for speed, values in self._speed_to_values.items():
              for value in values:
                    self._value_to_speed[value] = speed

    def _device_id(self):
        return (int(self.node.manufacturer_id, 16),
          int(self.node.product_id, 16))

    def update_properties(self):
        """Handle data changes for node values."""
        self._state = self._value_to_speed[self.values.primary.data]

    def set_speed(self, speed):
        """Set the speed of the fan."""
        value_range = self._speed_to_values[speed]
        midpoint = value_range[int(len(value_range) / 2)]
        self.node.set_dimmer(self.values.primary.value_id, midpoint)

    def turn_on(self, speed=None, **kwargs):
        """Turn the device on."""
        if speed is None:
            # Value 255 tells device to return to previous value
            self.node.set_dimmer(self.values.primary.value_id, 255)
        else:
            self.set_speed(speed)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.node.set_dimmer(self.values.primary.value_id, 0)

    @property
    def speed(self):
        """Return the current speed."""
        return self._state

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES
