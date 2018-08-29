"""
Platform to control a Salda Smarty XP/XV ventilation unit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.smarty/
"""
import logging

from homeassistant.core import callback
from homeassistant.components.fan import (
    SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF, SUPPORT_SET_SPEED,
    FanEntity)
from homeassistant.components.smarty import (
    DATA_SMARTY, Smarty, SIGNAL_UPDATE_SMARTY)
from homeassistant.const import (STATE_OFF, STATE_ON)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

DEPENDENCIES = ['smarty']

_LOGGER = logging.getLogger(__name__)

SPEED_LIST = [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

SPEED_MAPPING = {
    0: SPEED_OFF,
    1: SPEED_LOW,
    2: SPEED_MEDIUM,
    3: SPEED_HIGH
}

SPEED_TO_MODE = {
    SPEED_OFF: 0,
    SPEED_LOW: 1,
    SPEED_MEDIUM: 2,
    SPEED_HIGH: 3
}


async def async_setup_platform(hass, config,
                               async_add_devices, discovery_info=None):
    """Set up the Smarty Fan Platform."""
    smarty = hass.data[DATA_SMARTY]

    async_add_devices([SmartyFan(smarty.name, smarty)])


class SmartyFan(FanEntity):
    """Representation of a Smarty Fan."""

    def __init__(self, name: str, smarty: Smarty):
        """Initialize the entity."""
        self._name = name
        self._speed = SPEED_OFF
        self._state = None
        self._smarty = smarty

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def name(self):
        """Return the name of the fan."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:air-conditioner'

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed_list(self) -> list:
        """List of available fan modes."""
        return SPEED_LIST

    @property
    def is_on(self):
        """Return state of the fan."""
        return self._state == STATE_ON

    @property
    def speed(self) -> str:
        """Return speed of the fan."""
        return self._speed

    def turn_on(self, speed: str = None, **kwargs):
        """Turn on the fan."""
        _LOGGER.debug('Turning on fan.')
        if speed is None:
            speed = SPEED_MEDIUM
        self.set_speed(speed)
        if speed == SPEED_OFF:
            self._state = STATE_OFF
        else:
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn off the fan."""
        _LOGGER.debug('Turning off fan.')
        self.set_speed(SPEED_OFF)
        self._state = STATE_OFF

    def set_speed(self, speed: str) -> None:
        """Set fan speed."""
        _LOGGER.debug('Changing fan speed to %s.', speed)
        if speed in SPEED_LIST:
            mode = SPEED_TO_MODE.get(speed)
            _LOGGER.debug('Mode is %s', mode)
            self._smarty.set_fan_mode(mode)
            self._speed = speed

        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """Call to update fan."""
        async_dispatcher_connect(self.hass,
                                 SIGNAL_UPDATE_SMARTY,
                                 self._update_callback)

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    def update(self) -> None:
        """Update state."""
        _LOGGER.debug('Updating state')
        result = self._smarty.get_fan_mode()
        try:
            self._speed = SPEED_MAPPING[result]
            _LOGGER.debug('Speed/Mode is %s/%s', self._speed, result)
            if self._speed == SPEED_OFF:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
        except KeyError:
            _LOGGER.debug('Cannot update. Speed/State %s/%s',
                          self._speed, self._state)
            self._state = None
