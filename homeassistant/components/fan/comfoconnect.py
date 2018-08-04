"""
Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/fan.comfoconnect/
"""
import logging

from homeassistant.components.comfoconnect import (
    DOMAIN, ComfoConnectBridge, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED)
from homeassistant.components.fan import (
    FanEntity, SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH,
    SUPPORT_SET_SPEED)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.dispatcher import (dispatcher_connect)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['comfoconnect']

SPEED_MAPPING = {
    0: SPEED_OFF,
    1: SPEED_LOW,
    2: SPEED_MEDIUM,
    3: SPEED_HIGH
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ComfoConnect fan platform."""
    ccb = hass.data[DOMAIN]

    add_devices([ComfoConnectFan(hass, name=ccb.name, ccb=ccb)], True)


class ComfoConnectFan(FanEntity):
    """Representation of the ComfoConnect fan platform."""

    def __init__(self, hass, name, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect fan."""
        from pycomfoconnect import SENSOR_FAN_SPEED_MODE

        self._ccb = ccb
        self._name = name

        # Ask the bridge to keep us updated
        self._ccb.comfoconnect.register_sensor(SENSOR_FAN_SPEED_MODE)

        def _handle_update(var):
            if var == SENSOR_FAN_SPEED_MODE:
                _LOGGER.debug("Dispatcher update for %s", var)
                self.schedule_update_ha_state()

        # Register for dispatcher updates
        dispatcher_connect(
            hass, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, _handle_update)

    @property
    def name(self):
        """Return the name of the fan."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return 'mdi:air-conditioner'

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self):
        """Return the current fan mode."""
        from pycomfoconnect import (SENSOR_FAN_SPEED_MODE)

        try:
            speed = self._ccb.data[SENSOR_FAN_SPEED_MODE]
            return SPEED_MAPPING[speed]
        except KeyError:
            return STATE_UNKNOWN

    @property
    def speed_list(self):
        """List of available fan modes."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    def turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed is None:
            speed = SPEED_LOW
        self.set_speed(speed)

    def turn_off(self, **kwargs) -> None:
        """Turn off the fan (to away)."""
        self.set_speed(SPEED_OFF)

    def set_speed(self, speed: str):
        """Set fan speed."""
        _LOGGER.debug('Changing fan speed to %s.', speed)

        from pycomfoconnect import (
            CMD_FAN_MODE_AWAY, CMD_FAN_MODE_LOW, CMD_FAN_MODE_MEDIUM,
            CMD_FAN_MODE_HIGH)

        if speed == SPEED_OFF:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_AWAY)
        elif speed == SPEED_LOW:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_LOW)
        elif speed == SPEED_MEDIUM:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_MEDIUM)
        elif speed == SPEED_HIGH:
            self._ccb.comfoconnect.cmd_rmi_request(CMD_FAN_MODE_HIGH)

        # Update current mode
        self.schedule_update_ha_state()
