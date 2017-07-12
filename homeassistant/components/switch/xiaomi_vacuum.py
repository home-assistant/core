"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_vacuum/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import (DOMAIN, SwitchDevice,
                                             PLATFORM_SCHEMA)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (DEVICE_DEFAULT_NAME, CONF_NAME,
                                 CONF_HOST, CONF_TOKEN)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME): cv.string,
})

REQUIREMENTS = ['python-mirobo==0.1.1']

ATTR_COMMAND = 'command'
ATTR_PARAMS = 'params'
SERVICE_COMMAND = 'xiaomi_vacuum_command'

ATTR_FANSPEED = 'fanspeed'
SERVICE_FANSPEED = 'xiaomi_vacuum_set_fanspeed'

SERVICE_START_REMOTE_CONTROL = 'xiaomi_vacuum_remote_control_start'
SERVICE_MOVE_REMOTE_CONTROL = 'xiaomi_vacuum_remote_control_move'
SERVICE_STOP_REMOTE_CONTROL = 'xiaomi_vacuum_remote_control_stop'
SERVICE_REMOTE_CONTROL = 'xiaomi_vacuum_remote_control'

ATTR_RC_VELOCITY = 'velocity'
ATTR_RC_ROTATION = 'rotation'
ATTR_RC_DURATION = 'duration'

COMMAND_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): cv.string,
})

FANSPEED_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_FANSPEED): vol.All(vol.Coerce(int),
                                         vol.Range(min=0, max=100)),
})

REMOTE_CONTROL_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_RC_VELOCITY): vol.All(vol.Coerce(float),
                                            vol.Range(min=-0.3, max=0.3)),
    vol.Optional(ATTR_RC_ROTATION): vol.All(vol.Coerce(int),
                                            vol.Range(min=-179, max=179)),
    vol.Optional(ATTR_RC_DURATION): cv.positive_int,
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the vacuum from config."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    mirobo = MiroboSwitch(name, host, token)

    add_devices_callback([mirobo])

    def send_command_service(service):
        """Send command."""
        command = service.data.get(ATTR_COMMAND)
        params = service.data.get(ATTR_PARAMS)

        mirobo.raw_command(command, params)

    def set_fan_speed_service(service):
        """Set fan speed."""
        fan_speed = service.data.get(ATTR_FANSPEED)

        mirobo.set_fanspeed(fan_speed)

    def remote_control_start_service(service):
        """Start remote control of the vacuum."""
        mirobo.remote_control_start()

    def remote_control_stop_service(service):
        """Stop remote control of the vacuum."""
        mirobo.remote_control_stop()

    def remote_control_move_service(service):
        """Move the vacuum while remote control mode started."""
        velocity = service.data.get(ATTR_RC_VELOCITY)
        rotation = service.data.get(ATTR_RC_ROTATION)
        duration = service.data.get(ATTR_RC_DURATION)

        mirobo.remote_control_move(velocity=velocity, rotation=rotation,
                                   duration=duration)

    def remote_control_service(service):
        """Remote control the vacuum."""
        velocity = service.data.get(ATTR_RC_VELOCITY)
        rotation = service.data.get(ATTR_RC_ROTATION)
        duration = service.data.get(ATTR_RC_DURATION)

        mirobo.remote_control(velocity=velocity, rotation=rotation,
                              duration=duration)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_COMMAND,
                           send_command_service,
                           descriptions.get(SERVICE_COMMAND),
                           schema=COMMAND_SERVICE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_FANSPEED,
                           set_fan_speed_service,
                           descriptions.get(SERVICE_FANSPEED),
                           schema=FANSPEED_SERVICE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_START_REMOTE_CONTROL,
                           remote_control_start_service,
                           descriptions.get(SERVICE_START_REMOTE_CONTROL))

    hass.services.register(DOMAIN, SERVICE_STOP_REMOTE_CONTROL,
                           remote_control_stop_service,
                           descriptions.get(SERVICE_STOP_REMOTE_CONTROL))

    hass.services.register(DOMAIN, SERVICE_MOVE_REMOTE_CONTROL,
                           remote_control_move_service,
                           descriptions.get(SERVICE_MOVE_REMOTE_CONTROL),
                           schema=REMOTE_CONTROL_SERVICE_SCHEMA)

    hass.services.register(DOMAIN, SERVICE_REMOTE_CONTROL,
                           remote_control_service,
                           descriptions.get(SERVICE_REMOTE_CONTROL),
                           schema=REMOTE_CONTROL_SERVICE_SCHEMA)


class MiroboSwitch(SwitchDevice):
    """Representation of a Xiaomi Vacuum."""

    def __init__(self, name, host, token):
        """Initialize the vacuum switch."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._icon = 'mdi:broom'
        self.host = host
        self.token = token

        self._vacuum = None
        self._state = None
        self._state_attrs = {}
        self._is_on = False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def vacuum(self):
        """Property accessor for vacuum object."""
        if not self._vacuum:
            from mirobo import Vacuum
            _LOGGER.info("initializing with host %s token %s",
                         self.host, self.token)
            self._vacuum = Vacuum(self.host, self.token)

        return self._vacuum

    def raw_command(self, command, params):
        """Send command."""
        from mirobo import VacuumException
        try:
            self.vacuum.raw_command(command, params)
        except VacuumException as ex:
            _LOGGER.error("Unable to send command to the vacuum: %s", ex)

    def remote_control_start(self):
        """Start remote control."""
        from mirobo import VacuumException
        try:
            self.vacuum.manual_start()
        except VacuumException as ex:
            _LOGGER.error("Unable to start remote control the vacuum: %s", ex)

    def remote_control_stop(self):
        """Stop remote control."""
        from mirobo import VacuumException
        try:
            self.vacuum.manual_stop()
        except VacuumException as ex:
            _LOGGER.error("Unable to stop remote control the vacuum: %s", ex)

    def remote_control_move(self, rotation: int=0, velocity: float=0.3,
                            duration: int=1500):
        """Move vacuum with remote control."""
        from mirobo import VacuumException
        try:
            self.vacuum.manual_control(velocity=velocity, rotation=rotation,
                                       duration=duration)
        except VacuumException as ex:
            _LOGGER.error("Unable to move with remote control the vacuum: %s",
                          ex)

    def remote_control(self, rotation: int=0, velocity: float=0.3,
                       duration: int=1500):
        """Remote control."""
        from mirobo import VacuumException
        try:
            self.vacuum.manual_control_once(velocity=velocity,
                                            rotation=rotation,
                                            duration=duration)
        except VacuumException as ex:
            _LOGGER.error("Unable to remote control the vacuum: %s", ex)

    def set_fanspeed(self, speed):
        """Set the fanspeed."""
        from mirobo import VacuumException
        try:
            self.vacuum.set_fan_speed(speed)
        except VacuumException as ex:
            _LOGGER.error("Unable to set fanspeed: %s", ex)

    def turn_on(self, **kwargs):
        """Turn the vacuum on."""
        from mirobo import VacuumException
        try:
            self.vacuum.start()
            self._is_on = True
        except VacuumException as ex:
            _LOGGER.error("Unable to start the vacuum: %s", ex)

    def turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        from mirobo import VacuumException
        try:
            self.vacuum.stop()
            self.vacuum.home()
            self._is_on = False
        except VacuumException as ex:
            _LOGGER.error("Unable to turn off and return home: %s", ex)

    def update(self):
        """Fetch state from the device."""
        from mirobo import VacuumException
        try:
            state = self.vacuum.status()
            _LOGGER.debug("got state from the vacuum: %s", state)

            self._state_attrs = {
                'Status': state.state, 'Error': state.error,
                'Battery': state.battery, 'Fan': state.fanspeed,
                'Cleaning time': str(state.clean_time),
                'Cleaned area': state.clean_area}

            self._state = state.state_code
            self._is_on = state.is_on
        except VacuumException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)
