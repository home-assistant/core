"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/xiaomi_vacuum/
"""
import asyncio
from functools import partial
import logging
import os

import voluptuous as vol

from homeassistant.components.switch import SwitchDevice
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_TOKEN, CONF_SENSORS)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity


REQUIREMENTS = ['python-mirobo==0.1.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'xiaomi_vacuum'

SENSOR_MAP = {
    'state': ('Status', None, 'mdi:broom'),
    'error': ('Error', None, 'mdi:alert-circle'),
    'battery': ('Battery', '%', None),  # 'mdi:battery'
    'fanspeed': ('Fan', '%', 'mdi:fan'),
    'clean_time': ('Cleaning time', None, 'mdi:clock'),
    'clean_area': ('Cleaned area', 'm²', 'mdi:flip-to-back'),
}

ATTR_COMMAND = 'command'
ATTR_FANSPEED = 'fanspeed'
ATTR_PARAMS = 'params'
ATTR_RC_VELOCITY = 'velocity'
ATTR_RC_ROTATION = 'rotation'
ATTR_RC_DURATION = 'duration'

DEFAULT_NAME = 'Xiaomi Vacuum cleaner'
ICON = 'mdi:google-circles-group'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SENSORS):
            cv.ensure_list(vol.All(str, vol.In(SENSOR_MAP))),
    })
}, extra=vol.ALLOW_EXTRA)

SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SET_FANSPEED = 'set_fanspeed'
SERVICE_MOVE_REMOTE_CONTROL = 'remote_control_move'
SERVICE_MOVE_REMOTE_CONTROL_STEP = 'remote_control_move_step'
SERVICE_START_REMOTE_CONTROL = 'remote_control_start'
SERVICE_STOP_REMOTE_CONTROL = 'remote_control_stop'

SERVICE_SCHEMA_SEND_COMMAND = vol.Schema({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): cv.string,
})

SERVICE_SCHEMA_SET_FANSPEED = vol.Schema({
    vol.Required(ATTR_FANSPEED):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

SERVICE_SCHEMA_REMOTE_CONTROL = vol.Schema({
    vol.Optional(ATTR_RC_VELOCITY):
        vol.All(vol.Coerce(float), vol.Range(min=-0.3, max=0.3)),
    vol.Optional(ATTR_RC_ROTATION):
        vol.All(vol.Coerce(int), vol.Range(min=-179, max=179)),
    vol.Optional(ATTR_RC_DURATION): cv.positive_int,
})

SERVICE_MAP = {
    SERVICE_SEND_COMMAND: SERVICE_SCHEMA_SEND_COMMAND,
    SERVICE_SET_FANSPEED: SERVICE_SCHEMA_SET_FANSPEED,
    SERVICE_START_REMOTE_CONTROL: {},
    SERVICE_STOP_REMOTE_CONTROL: {},
    SERVICE_MOVE_REMOTE_CONTROL: SERVICE_SCHEMA_REMOTE_CONTROL,
    SERVICE_MOVE_REMOTE_CONTROL_STEP: SERVICE_SCHEMA_REMOTE_CONTROL
}

SIGNAL_UPDATE_DATA = DOMAIN + '_update'


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the xiaomi vacuum component."""
    if not config[DOMAIN]:
        return False

    config = config[DOMAIN]
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    sensors = config.get(CONF_SENSORS)

    # Create handler
    mirobo = MiroboVacuum(hass, host, token)
    hass.data[DOMAIN] = mirobo

    # Add entities
    yield from hass.async_add_job(
        async_load_platform(hass, 'switch', DOMAIN, {CONF_NAME: name}))

    if sensors:
        yield from hass.async_add_job(
            async_load_platform(hass, 'sensor', DOMAIN,
                                {CONF_NAME: name, CONF_SENSORS: sensors}))

    @asyncio.coroutine
    def async_vacuum_service_call(service):
        """Handle service calls to the xiaomi vacuum component."""
        kwargs = dict(service.data)
        if service.service == SERVICE_SEND_COMMAND:
            yield from hass.async_add_job(
                mirobo.raw_command,
                kwargs[ATTR_COMMAND], kwargs.get(ATTR_PARAMS))
        elif service.service == SERVICE_SET_FANSPEED:
            yield from hass.async_add_job(
                mirobo.set_fanspeed, kwargs[ATTR_FANSPEED])
        elif service.service == SERVICE_START_REMOTE_CONTROL:
            yield from hass.async_add_job(mirobo.remote_control_start)
        elif service.service == SERVICE_STOP_REMOTE_CONTROL:
            yield from hass.async_add_job(mirobo.remote_control_stop)
        elif service.service == SERVICE_MOVE_REMOTE_CONTROL:
            yield from hass.async_add_job(
                partial(mirobo.remote_control_move, **kwargs))
        else:  # elif service.service == SERVICE_MOVE_REMOTE_CONTROL_STEP:
            yield from hass.async_add_job(
                partial(mirobo.remote_control_move_step, **kwargs))

    # Register vacuum services
    descriptions = yield from hass.async_add_job(
        load_yaml_config_file,
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    for vacuum_service, schema in SERVICE_MAP.items():
        hass.services.async_register(
            DOMAIN, vacuum_service, async_vacuum_service_call,
            descriptions.get(vacuum_service), schema=schema)

    return True


class MiroboVacuum:
    """Representation of a Xiaomi Vacuum cleaner robot."""

    def __init__(self, hass, host, token):
        """Initialize the vacuum switch."""
        self.hass = hass
        self.host = host
        self.token = token
        self._vacuum = None

        self.state = None
        self.state_attrs = {}
        self.is_on = False
        self.available = False

    @property
    def vacuum(self):
        """Property accessor for vacuum object."""
        if not self._vacuum:
            from mirobo import Vacuum
            _LOGGER.info("Initializing with host %s (token %s...)",
                         self.host, self.token[:5])
            self._vacuum = Vacuum(self.host, self.token)

        return self._vacuum

    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        from mirobo import VacuumException
        try:
            func(*args, **kwargs)
            self.available = True
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_DATA)
            return True
        except VacuumException as ex:
            _LOGGER.error(mask_error, ex)
            return False

    def raw_command(self, command, params):
        """Send raw command."""
        self._try_command(
            "Unable to send command to the vacuum: %s",
            self.vacuum.raw_command, command, params)

    def remote_control_start(self):
        """Start remote control mode."""
        self._try_command(
            "Unable to start remote control the vacuum: %s",
            self.vacuum.manual_start)

    def remote_control_stop(self):
        """Stop remote control mode."""
        self._try_command(
            "Unable to stop remote control the vacuum: %s",
            self.vacuum.manual_stop)

    def remote_control_move(self, rotation: int=0, velocity: float=0.3,
                            duration: int=1500):
        """Move vacuum with remote control mode."""
        self._try_command(
            "Unable to move with remote control the vacuum: %s",
            self.vacuum.manual_control,
            velocity=velocity, rotation=rotation, duration=duration)

    def remote_control_move_step(self, rotation: int=0,
                                 velocity: float=0.3, duration: int=1500):
        """Move vacuum one step with remote control mode."""
        self._try_command(
            "Unable to remote control the vacuum: %s",
            self.vacuum.manual_control_once,
            velocity=velocity, rotation=rotation, duration=duration)

    def set_fanspeed(self, speed):
        """Set the fanspeed."""
        self._try_command(
            "Unable to set fanspeed: %s", self.vacuum.set_fan_speed, speed)

    def turn_on_cleaning(self, **kwargs):
        """Turn the vacuum on."""
        if self._try_command(
                "Unable to start the vacuum: %s", self.vacuum.start):
            self.is_on = True

    def turn_off_cleaning(self, **kwargs):
        """Turn the vacuum off and return to home."""
        if (self._try_command(
                "Unable to turn off: %s", self.vacuum.stop) and
                self._try_command(
                    "Unable to return home: %s", self.vacuum.home)):
            self.is_on = False

    def update_vacuum_state(self):
        """Fetch state from the device."""
        from mirobo import DeviceException
        try:
            state = self.vacuum.status()
            _LOGGER.debug("Got new state from the vacuum: %s", state)
            self.state_attrs = {
                'Status': state.state, 'Error': state.error,
                'Battery': state.battery, 'Fan': state.fanspeed,
                'Cleaning time': str(state.clean_time),
                'Cleaned area': state.clean_area}
            self.state = state
            self.is_on = state.is_on
            self.available = True
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_DATA)
        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)
            self.available = False


class MiroboVacuumSwitch(SwitchDevice):
    """Representation of the master switch of a Xiaomi Vacuum cleaner."""

    def __init__(self, name, mirobo_vacuum, icon):
        """Initialize the vacuum switch."""
        self._name = name
        self._icon = icon
        self._handler = mirobo_vacuum

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
        return self._handler.state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._handler.state_attrs

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._handler.is_on

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        yield from self.hass.async_add_job(self._handler.turn_on_cleaning)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        yield from self.hass.async_add_job(self._handler.turn_off_cleaning)

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        yield from self.hass.async_add_job(self._handler.update_vacuum_state)


class MiroboVacuumSensor(Entity):
    """Representation of a sensor of a Xiaomi Vacuum cleaner."""

    def __init__(self, mirobo_vacuum, name, sensor_type):
        """Initialize the sensor object."""
        self._handler = mirobo_vacuum
        self._sensor = sensor_type

        friendly_name, unit, icon = SENSOR_MAP[sensor_type]
        self._name = '{}_{}'.format(name, sensor_type)
        self._friendly_name = friendly_name
        self._icon = icon
        self._unit = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self._handler.state, self._sensor)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self):
        """Return true when state is known."""
        return self._handler.state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {"friendly_name": self._friendly_name}
        return attrs

    @property
    def icon(self):
        """Return the icon for the sensor."""
        if self._sensor == 'battery':
            returning_icon = 'mdi:battery'
            if not self.available:
                return returning_icon + '-unknown'
            if getattr(self._handler.state, 'state') == 'Charging':
                returning_icon += '-charging'
            if 20 < self.state < 100:
                returning_icon += '-{}'.format(int(self.state / 20) * 20)
            elif self.state < 20:
                returning_icon += '-outline'
            return returning_icon
        return self._icon

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_sensor_update():
            """Update callback."""
            self.hass.async_add_job(self.async_update_ha_state(True))

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_DATA, async_sensor_update)
