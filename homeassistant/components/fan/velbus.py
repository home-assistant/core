"""
Support for Velbus platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.velbus/
"""
import asyncio
import logging
import voluptuous as vol

from homeassistant.components.fan import (
    SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH, FanEntity, SUPPORT_SET_SPEED,
    PLATFORM_SCHEMA)
from homeassistant.components.velbus import DOMAIN
from homeassistant.const import CONF_NAME, CONF_DEVICES, STATE_OFF
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['velbus']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
            vol.Required('module'): cv.positive_int,
            vol.Required('channel_low'): cv.positive_int,
            vol.Required('channel_medium'): cv.positive_int,
            vol.Required('channel_high'): cv.positive_int,
            vol.Required(CONF_NAME): cv.string,
        }
    ])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Fans."""
    velbus = hass.data[DOMAIN]
    add_devices(VelbusFan(fan, velbus) for fan in config[CONF_DEVICES])


class VelbusFan(FanEntity):
    """Representation of a Velbus Fan."""

    def __init__(self, fan, velbus):
        """Initialize a Velbus light."""
        self._velbus = velbus
        self._name = fan[CONF_NAME]
        self._module = fan['module']
        self._channel_low = fan['channel_low']
        self._channel_medium = fan['channel_medium']
        self._channel_high = fan['channel_high']
        self._channels = [self._channel_low, self._channel_medium,
                          self._channel_high]
        self._channels_state = [False, False, False]
        self._speed = STATE_OFF

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Add listener for Velbus messages on bus."""
        def _init_velbus():
            """Initialize Velbus on startup."""
            self._velbus.subscribe(self._on_message)
            self.get_status()

        yield from self.hass.async_add_job(_init_velbus)

    def _on_message(self, message):
        import velbus
        if isinstance(message, velbus.RelayStatusMessage) and \
           message.address == self._module and \
           message.channel in self._channels:
            if message.channel == self._channel_low:
                self._channels_state[0] = message.is_on()
            elif message.channel == self._channel_medium:
                self._channels_state[1] = message.is_on()
            elif message.channel == self._channel_high:
                self._channels_state[2] = message.is_on()
            self._calculate_speed()
            self.schedule_update_ha_state()

    def _calculate_speed(self):
        if self._is_off():
            self._speed = STATE_OFF
        elif self._is_low():
            self._speed = SPEED_LOW
        elif self._is_medium():
            self._speed = SPEED_MEDIUM
        elif self._is_high():
            self._speed = SPEED_HIGH

    def _is_off(self):
        return self._channels_state[0] is False and \
               self._channels_state[1] is False and \
               self._channels_state[2] is False

    def _is_low(self):
        return self._channels_state[0] is True and \
               self._channels_state[1] is False and \
               self._channels_state[2] is False

    def _is_medium(self):
        return self._channels_state[0] is True and \
               self._channels_state[1] is True and \
               self._channels_state[2] is False

    def _is_high(self):
        return self._channels_state[0] is True and \
               self._channels_state[1] is False and \
               self._channels_state[2] is True

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def speed(self):
        """Return the current speed."""
        return self._speed

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        return [STATE_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed=None, **kwargs):
        """Turn on the entity."""
        if speed is None:
            speed = SPEED_MEDIUM
        self.set_speed(speed)

    def turn_off(self, **kwargs):
        """Turn off the entity."""
        self.set_speed(STATE_OFF)

    def set_speed(self, speed):
        """Set the speed of the fan."""
        channels_off = []
        channels_on = []
        if speed == STATE_OFF:
            channels_off = self._channels
        elif speed == SPEED_LOW:
            channels_off = [self._channel_medium, self._channel_high]
            channels_on = [self._channel_low]
        elif speed == SPEED_MEDIUM:
            channels_off = [self._channel_high]
            channels_on = [self._channel_low, self._channel_medium]
        elif speed == SPEED_HIGH:
            channels_off = [self._channel_medium]
            channels_on = [self._channel_low, self._channel_high]
        for channel in channels_off:
            self._relay_off(channel)
        for channel in channels_on:
            self._relay_on(channel)
        self.schedule_update_ha_state()

    def _relay_on(self, channel):
        import velbus
        message = velbus.SwitchRelayOnMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self._velbus.send(message)

    def _relay_off(self, channel):
        import velbus
        message = velbus.SwitchRelayOffMessage()
        message.set_defaults(self._module)
        message.relay_channels = [channel]
        self._velbus.send(message)

    def get_status(self):
        """Retrieve current status."""
        import velbus
        message = velbus.ModuleStatusRequestMessage()
        message.set_defaults(self._module)
        message.channels = self._channels
        self._velbus.send(message)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_SET_SPEED
