"""Support for Lutron fans."""
import logging

from homeassistant.components.fan import (SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH, SPEED_OFF, SUPPORT_SET_SPEED, FanEntity)
# from homeassistant.const import (CONF_DEVICES, CONF_HOST, CONF_MAC, CONF_NAME, CONF_ID)

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

_LOGGER = logging.getLogger(__name__)

SPEED_MEDIUM_HIGH = 'medium_high'
SPEED_MAPPING = {
    SPEED_OFF: 0,
    SPEED_LOW: 25,
    SPEED_MEDIUM: 50,
    SPEED_MEDIUM_HIGH: 75,
    SPEED_HIGH: 100
}

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron fans."""
    devs = []

    for (area_name, device) in hass.data[LUTRON_DEVICES]['fan']:
        dev = LutronFan(area_name, device, hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)

class LutronFan(LutronDevice, FanEntity):
    """Representation of a Lutron Fan, including dimmable."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the fan."""
        self._area_name = str(area_name)
        self._name = str(area_name) + ' Fan'
        self._is_on = False
        self._speed = SPEED_OFF
        self._prev_speed = None
        super().__init__(area_name, lutron_device, controller)

    @property
    def is_on(self):
        """Return true if device is on."""
        # return self._lutron_device.last_level() > SPEED_OFF
        return self._is_on

    # @property
    # def speed(self) -> str:
    #     """Return the current speed."""
    #     return self._speed
    @property
    def speed(self):
        """Return the brightness of the fan."""
        new_speed = self._lutron_device.last_level()
        if new_speed != SPEED_OFF:
            self._prev_speed = new_speed
        return new_speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_MEDIUM_HIGH, SPEED_HIGH]

    @property
    # def state_attributes(self):
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {'lutron_integration_id': self._lutron_device.id}
        return attr

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    def turn_on(self, speed: str = None, **kwargs):
        """Instruct the fan to turn on."""
        if speed is None:
            speed = SPEED_HIGH
        self._prev_speed = speed
        self.set_speed(speed)
    
    def set_speed(self, speed: str):
        """Set speed of the fan"""
        self._speed = speed
        if speed not in SPEED_MAPPING:
            _LOGGER.debug("Unknown speed %s, setting to %s", speed, SPEED_HIGH)
            self._speed = SPEED_HIGH
        else:
            self._speed = self._prev_speed                                        # TODO returns 0.0 right now....
            # self._speed = SPEED_MAPPING[SPEED_MEDIUM_HIGH]
            print('+++++++++++++++++++++ ' +str(self._speed))
        self._lutron_device.level = SPEED_MAPPING[self._speed]

    def turn_off(self, **kwargs):
        """Turn the fan off."""
        self._lutron_device.level = SPEED_OFF

    def update_state(self, value):
        print('........Inside of update_state...')
        """Update internal state and fan speed."""
        if self._prev_speed is None:
            self._prev_speed = self._lutron_device.level

        self._is_on = value > SPEED_MAPPING[SPEED_OFF]
        if value in range(SPEED_MAPPING[SPEED_MEDIUM_HIGH] + 1, SPEED_MAPPING[SPEED_HIGH] + 1):
            self._speed = SPEED_HIGH
        elif value in range(SPEED_MAPPING[SPEED_MEDIUM] + 1, SPEED_MAPPING[SPEED_MEDIUM_HIGH] + 1):
            # 51% - 55% are missing from Lutron integration protocol
            # we will treat as medium_high
            self._speed = SPEED_MEDIUM_HIGH
        elif value in range(SPEED_MAPPING[SPEED_LOW] + 1, SPEED_MAPPING[SPEED_MEDIUM] + 1):
            self._speed = SPEED_MEDIUM
        elif value in range(SPEED_MAPPING[SPEED_OFF] + 1, SPEED_MAPPING[SPEED_LOW] + 1):
            self._speed = SPEED_LOW
        elif value == SPEED_MAPPING[SPEED_OFF]:
            self._speed = SPEED_OFF
        _LOGGER.debug("Fan speed is %s", self._speed)

    @property
    def name(self):
        """Return the display name of this fan."""
        return self._name
