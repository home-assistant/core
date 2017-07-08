"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_vacuum/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import DOMAIN, SwitchDevice, PLATFORM_SCHEMA
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (ATTR_ENTITY_ID, DEVICE_DEFAULT_NAME,
                                 CONF_NAME, CONF_HOST, CONF_TOKEN)

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME): cv.string,
})

REQUIREMENTS = ['python-mirobo==0.0.9']

ATTR_COMMAND = 'command'
ATTR_PARAMS = 'params'
SERVICE_COMMAND = 'xiaomi_vacuum_command'

ATTR_FANSPEED = 'fanspeed'
SERVICE_FANSPEED= 'xiaomi_vacuum_set_fanspeed'

ATTR_RC_SPEED = 'speed'
ATTR_RC_DIRECTION = 'direction'
ATTR_RC_DURATION = 'duration'
SERVICE_REMOTE_CONTROL = 'xiaomi_vacuum_remote_control'

COMMAND_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): cv.string,
})

FANSPEED_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_FANSPEED): vol.All(vol.Coerce(int), vol.Any(38, 60, 77)),
})

REMOTE_CONTROL_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_RC_SPEED): vol.All(vol.Coerce(float), vol.Range(min=-0.3, max=0.3)),
    vol.Required(ATTR_RC_DIRECTION): vol.All(vol.Coerce(float), vol.Range(min=-3.1, max=3.1)),
    vol.Required(ATTR_RC_DURATION): cv.positive_int,
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
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        command = service.data.get(ATTR_COMMAND)
        params = service.data.get(ATTR_PARAMS)

        mirobo.raw_command(command, params)

    def set_fan_speed_service(service):
        """Set fan speed."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        fan_speed = service.data.get(ATTR_FANSPEED)

        mirobo.set_fanspeed(fan_speed)

    def remote_control_service(service):
        """Remote control the vacuum."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        speed = service.data.get(ATTR_RC_SPEED)
        direction = service.data.get(ATTR_RC_DIRECTION)
        duration = service.data.get(ATTR_RC_DURATION)

        mirobo.remote_control(speed, direction, duration)

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

    def remote_control(self, speed, direction, duration):
        """Remote control."""
        from mirobo import VacuumException
        try:
            self.vacuum.rc_move_once(speed, direction, duration)
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