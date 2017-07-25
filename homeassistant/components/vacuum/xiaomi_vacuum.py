"""
Support for the Xiaomi vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.xiaomi_vacuum/
"""
import asyncio
from functools import partial
import logging
import os

import voluptuous as vol

from homeassistant.components.vacuum import (
    VacuumDevice, DOMAIN,
    DEFAULT_ICON, PLATFORM_SCHEMA, VACUUM_SERVICE_SCHEMA,
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_PAUSE, SUPPORT_RETURN_HOME,
    SUPPORT_STOP, SUPPORT_FANSPEED, SUPPORT_SENDCOMMAND, SUPPORT_LOCATE)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    STATE_ON, STATE_OFF, ATTR_ENTITY_ID,
    CONF_NAME, CONF_HOST, CONF_TOKEN, CONF_SENSORS)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_send, async_dispatcher_connect)
from homeassistant.helpers.entity import Entity
from homeassistant.util.icon import icon_for_battery_level

REQUIREMENTS = ['python-mirobo==0.1.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Vacuum cleaner'
ICON = 'mdi:google-circles-group'
PLATFORM = 'xiaomi_vacuum'

SENSOR_MAP = {
    'state': ('Status', None, 'mdi:broom'),
    'error': ('Error', None, 'mdi:alert-circle'),
    'battery': ('Battery', '%', None),  # 'mdi:battery'
    'fanspeed': ('Fan', '%', 'mdi:fan'),
    'clean_time': ('Cleaning time', None, 'mdi:clock'),
    'clean_area': ('Cleaned area', 'm²', 'mdi:flip-to-back'),
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SENSORS):
        cv.ensure_list(vol.All(str, vol.In(SENSOR_MAP))),
}, extra=vol.ALLOW_EXTRA)

SERVICE_MOVE_REMOTE_CONTROL = 'xiaomi_remote_control_move'
SERVICE_MOVE_REMOTE_CONTROL_STEP = 'xiaomi_remote_control_move_step'
SERVICE_START_REMOTE_CONTROL = 'xiaomi_remote_control_start'
SERVICE_STOP_REMOTE_CONTROL = 'xiaomi_remote_control_stop'

ATTR_RC_VELOCITY = 'velocity'
ATTR_RC_ROTATION = 'rotation'
ATTR_RC_DURATION = 'duration'

SERVICE_SCHEMA_REMOTE_CONTROL = VACUUM_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_RC_VELOCITY):
        vol.All(vol.Coerce(float), vol.Range(min=-0.29, max=0.29)),
    vol.Optional(ATTR_RC_ROTATION):
        vol.All(vol.Coerce(int), vol.Range(min=-179, max=179)),
    vol.Optional(ATTR_RC_DURATION): cv.positive_int,
})

SERVICE_TO_METHOD = {
    SERVICE_START_REMOTE_CONTROL: {'method': 'async_start_remote_control'},
    SERVICE_STOP_REMOTE_CONTROL: {'method': 'async_stop_remote_control'},
    SERVICE_MOVE_REMOTE_CONTROL: {
        'method': 'async_move_remote_control',
        'schema': SERVICE_SCHEMA_REMOTE_CONTROL},
    SERVICE_MOVE_REMOTE_CONTROL_STEP: {
        'method': 'async_move_remote_control_step',
        'schema': SERVICE_SCHEMA_REMOTE_CONTROL},
}

SUPPORT_XIAOMI = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PAUSE | \
                 SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_FANSPEED | \
                 SUPPORT_SENDCOMMAND | SUPPORT_LOCATE

SIGNAL_UPDATE_DATA = PLATFORM + '_update'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Xiaomi vacuum cleaner robot platform."""
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    sensors = config.get(CONF_SENSORS)

    # Create handler
    mirobo = MiroboVacuum(hass, name, host, token)
    hass.data[PLATFORM][host] = mirobo

    # Add asociated sensors as new entities
    if sensors:
        yield from hass.async_add_job(
            async_load_platform(
                hass, 'sensor', PLATFORM,
                {CONF_NAME: name, CONF_HOST: host, CONF_SENSORS: sensors}))

    async_add_devices([mirobo], update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on MiroboVacuum."""
        _LOGGER.debug('XIAOMI async_service_handler -> %s, %s',
                      service.service, service.data)
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            return

        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            target_vacuums = [vac for vac in hass.data[PLATFORM].values()
                              if vac.entity_id in entity_ids]
        else:
            target_vacuums = hass.data[PLATFORM].values()

        update_tasks = []
        for vacuum in target_vacuums:
            yield from getattr(vacuum, method['method'])(**params)

        for vacuum in target_vacuums:
            if vacuum.should_poll:
                update_coro = vacuum.async_update_ha_state(True)
                update_tasks.append(update_coro)

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    for vacuum_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[vacuum_service].get(
            'schema', VACUUM_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, vacuum_service, async_service_handler,
            description=descriptions.get(vacuum_service), schema=schema)


class MiroboVacuum(VacuumDevice):
    """Representation of a Xiaomi Vacuum cleaner robot."""

    def __init__(self, hass, name, host, token):
        """Initialize the Xiaomi vacuum cleaner robot handler."""
        self.hass = hass
        self._name = name
        self._icon = DEFAULT_ICON
        self._host = host
        self._token = token
        self._vacuum = None

        self._state_attrs = {}
        self.vacuum_state = None
        self._is_on = False
        self._available = False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return self._icon

    # @property
    # def should_poll(self):
    #     """Return True if entity has to be polled for state."""
    #     return False

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def vacuum(self):
        """Property accessor for vacuum object."""
        if not self._vacuum:
            from mirobo import Vacuum
            _LOGGER.info("Initializing with host %s (token %s...)",
                         self._host, self._token[:5])
            self._vacuum = Vacuum(self._host, self._token)

        return self._vacuum

    @property
    def state(self) -> str:
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_XIAOMI

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a vacuum command handling error messages."""
        from mirobo import VacuumException
        try:
            yield from self.hass.async_add_job(partial(func, *args, **kwargs))
            return True
        except VacuumException as ex:
            _LOGGER.error(mask_error, ex)
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        is_on = yield from self._try_command(
            "Unable to start the vacuum: %s", self.vacuum.start)
        self._is_on = is_on

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        yield from self.async_stop()
        return_home = yield from self.async_return_to_base()
        if return_home:
            self._is_on = False

    @asyncio.coroutine
    def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        yield from self._try_command(
            "Unable to stop: %s", self.vacuum.stop)

    @asyncio.coroutine
    def async_set_fanspeed(self, fanspeed=60, **kwargs):
        """Set the fanspeed."""
        yield from self._try_command(
            "Unable to set fanspeed: %s", self.vacuum.set_fan_speed, fanspeed)

    @asyncio.coroutine
    def async_cleaning_play_pause(self, **kwargs):
        """Pause the cleaning task or replay it."""
        if self.vacuum_state and self.is_on:
            yield from self._try_command(
                "Unable to set play/pause: %s", self.vacuum.pause)
        else:
            yield from self.async_turn_on()

    @asyncio.coroutine
    def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        return_home = yield from self._try_command(
            "Unable to return home: %s", self.vacuum.home)
        if return_home:
            self._is_on = False

    @asyncio.coroutine
    def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        yield from self._try_command(
            "Unable to locate the botvac: %s", self.vacuum.find)

    @asyncio.coroutine
    def async_send_command(self, command, params, **kwargs):
        """Send raw command."""
        _LOGGER.debug('async_send_command %s (%s), %s',
                      command, params, kwargs)
        yield from self._try_command(
            "Unable to send command to the vacuum: %s",
            self.vacuum.raw_command, command, params)

    @asyncio.coroutine
    def async_remote_control_start(self):
        """Start remote control mode."""
        yield from self._try_command(
            "Unable to start remote control the vacuum: %s",
            self.vacuum.manual_start)

    @asyncio.coroutine
    def async_remote_control_stop(self):
        """Stop remote control mode."""
        yield from self._try_command(
            "Unable to stop remote control the vacuum: %s",
            self.vacuum.manual_stop)

    @asyncio.coroutine
    def async_remote_control_move(self,
                                  rotation: int=0,
                                  velocity: float=0.3,
                                  duration: int=1500):
        """Move vacuum with remote control mode."""
        _LOGGER.debug('async_remote_control_move -> %s,%s,%s',
                      rotation, velocity, duration)
        yield from self._try_command(
            "Unable to move with remote control the vacuum: %s",
            self.vacuum.manual_control,
            velocity=velocity, rotation=rotation, duration=duration)

    @asyncio.coroutine
    def async_remote_control_move_step(self,
                                       rotation: int=0,
                                       velocity: float=0.2,
                                       duration: int=1500):
        """Move vacuum one step with remote control mode."""
        _LOGGER.debug('async_remote_control_move_step -> %s,%s,%s',
                      rotation, velocity, duration)
        yield from self._try_command(
            "Unable to remote control the vacuum: %s",
            self.vacuum.manual_control_once,
            velocity=velocity, rotation=rotation, duration=duration)

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from mirobo import DeviceException
        try:
            state = yield from self.hass.async_add_job(self.vacuum.status)

            _LOGGER.debug("Got new state from the vacuum: %s", state)
            self._state_attrs = {
                'Status': state.state, 'Error': state.error,
                'Battery': state.battery, 'Fan': state.fanspeed,
                'Cleaning time': str(state.clean_time),
                'Cleaned area': state.clean_area}
            self.vacuum_state = state
            self._is_on = state.is_on
            self._available = True
            async_dispatcher_send(self.hass, SIGNAL_UPDATE_DATA)
        except DeviceException as ex:
            _LOGGER.warning("Got exception while fetching the state: %s", ex)
            self._available = False
        except OSError as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)
            self._available = False


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
        return getattr(self._handler.vacuum_state, self._sensor)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self):
        """Return true when state is known."""
        return self._handler.available

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {"friendly_name": self._friendly_name}
        return attrs

    @property
    def icon(self):
        """Return the icon for the sensor."""
        if self._sensor == 'battery':
            return icon_for_battery_level(
                battery_level=self.state,
                charging=getattr(
                    self._handler.vacuum_state, 'state') == 'Charging')
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
