"""
Support for the Xiaomi vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.xiaomi_miio/
"""
import asyncio
from functools import partial
import logging
import os

import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA, DOMAIN, PLATFORM_SCHEMA, SUPPORT_BATTERY,
    SUPPORT_CLEAN_SPOT, SUPPORT_FAN_SPEED, SUPPORT_LOCATE, SUPPORT_PAUSE,
    SUPPORT_RETURN_HOME, SUPPORT_SEND_COMMAND, SUPPORT_STATUS, SUPPORT_STOP,
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, VACUUM_SERVICE_SCHEMA, VacuumDevice)
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_HOST, CONF_NAME, CONF_TOKEN, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-miio==0.3.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Vacuum cleaner'
ICON = 'mdi:google-circles-group'
PLATFORM = 'xiaomi_miio'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}, extra=vol.ALLOW_EXTRA)

SERVICE_MOVE_REMOTE_CONTROL = 'xiaomi_remote_control_move'
SERVICE_MOVE_REMOTE_CONTROL_STEP = 'xiaomi_remote_control_move_step'
SERVICE_START_REMOTE_CONTROL = 'xiaomi_remote_control_start'
SERVICE_STOP_REMOTE_CONTROL = 'xiaomi_remote_control_stop'

FAN_SPEEDS = {
    'Quiet': 38,
    'Balanced': 60,
    'Turbo': 77,
    'Max': 90}

ATTR_CLEANING_TIME = 'cleaning_time'
ATTR_DO_NOT_DISTURB = 'do_not_disturb'
ATTR_DO_NOT_DISTURB_START = 'do_not_disturb_start'
ATTR_DO_NOT_DISTURB_END = 'do_not_disturb_end'
ATTR_MAIN_BRUSH_LEFT = 'main_brush_left'
ATTR_SIDE_BRUSH_LEFT = 'side_brush_left'
ATTR_FILTER_LEFT = 'filter_left'
ATTR_CLEANING_COUNT = 'cleaning_count'
ATTR_CLEANED_TOTAL_AREA = 'total_cleaned_area'
ATTR_CLEANING_TOTAL_TIME = 'total_cleaning_time'
ATTR_ERROR = 'error'
ATTR_RC_DURATION = 'duration'
ATTR_RC_ROTATION = 'rotation'
ATTR_RC_VELOCITY = 'velocity'

SERVICE_SCHEMA_REMOTE_CONTROL = VACUUM_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_RC_VELOCITY):
        vol.All(vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)),
    vol.Optional(ATTR_RC_ROTATION):
        vol.All(vol.Coerce(int), vol.Clamp(min=-179, max=179)),
    vol.Optional(ATTR_RC_DURATION): cv.positive_int,
})

SERVICE_TO_METHOD = {
    SERVICE_START_REMOTE_CONTROL: {'method': 'async_remote_control_start'},
    SERVICE_STOP_REMOTE_CONTROL: {'method': 'async_remote_control_stop'},
    SERVICE_MOVE_REMOTE_CONTROL: {
        'method': 'async_remote_control_move',
        'schema': SERVICE_SCHEMA_REMOTE_CONTROL},
    SERVICE_MOVE_REMOTE_CONTROL_STEP: {
        'method': 'async_remote_control_move_step',
        'schema': SERVICE_SCHEMA_REMOTE_CONTROL},
}

SUPPORT_XIAOMI = SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PAUSE | \
                 SUPPORT_STOP | SUPPORT_RETURN_HOME | SUPPORT_FAN_SPEED | \
                 SUPPORT_SEND_COMMAND | SUPPORT_LOCATE | \
                 SUPPORT_STATUS | SUPPORT_BATTERY | SUPPORT_CLEAN_SPOT


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Xiaomi vacuum cleaner robot platform."""
    from miio import Vacuum
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    # Create handler
    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    vacuum = Vacuum(host, token)

    mirobo = MiroboVacuum(name, vacuum)
    hass.data[PLATFORM][host] = mirobo

    async_add_devices([mirobo], update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on MiroboVacuum."""
        method = SERVICE_TO_METHOD.get(service.service)
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

    def __init__(self, name, vacuum):
        """Initialize the Xiaomi vacuum cleaner robot handler."""
        self._name = name
        self._icon = ICON
        self._vacuum = vacuum

        self.vacuum_state = None
        self._is_on = False
        self._available = False

        self.consumable_state = None
        self.clean_history = None
        self.dnd_state = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device."""
        return self._icon

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        if self.vacuum_state is not None:
            return self.vacuum_state.state

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        if self.vacuum_state is not None:
            return self.vacuum_state.battery

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        if self.vacuum_state is not None:
            speed = self.vacuum_state.fanspeed
            if speed in FAN_SPEEDS.values():
                return [key for key, value in FAN_SPEEDS.items()
                        if value == speed][0]
            return speed

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(sorted(FAN_SPEEDS.keys(), key=lambda s: FAN_SPEEDS[s]))

    @property
    def device_state_attributes(self):
        """Return the specific state attributes of this vacuum cleaner."""
        attrs = {}
        if self.vacuum_state is not None:
            attrs.update({
                ATTR_DO_NOT_DISTURB:
                    STATE_ON if self.dnd_state.enabled else STATE_OFF,
                ATTR_DO_NOT_DISTURB_START: str(self.dnd_state.start),
                ATTR_DO_NOT_DISTURB_END: str(self.dnd_state.end),
                # Not working --> 'Cleaning mode':
                #    STATE_ON if self.vacuum_state.in_cleaning else STATE_OFF,
                ATTR_CLEANING_TIME: int(
                    self.vacuum_state.clean_time.total_seconds()
                    / 60),
                ATTR_CLEANED_AREA: int(self.vacuum_state.clean_area),
                ATTR_CLEANING_COUNT: int(self.clean_history.count),
                ATTR_CLEANED_TOTAL_AREA: int(self.clean_history.total_area),
                ATTR_CLEANING_TOTAL_TIME: int(
                    self.clean_history.total_duration.total_seconds()
                    / 60),
                ATTR_MAIN_BRUSH_LEFT: int(
                    self.consumable_state.main_brush_left.total_seconds()
                    / 3600),
                ATTR_SIDE_BRUSH_LEFT: int(
                    self.consumable_state.side_brush_left.total_seconds()
                    / 3600),
                ATTR_FILTER_LEFT: int(
                    self.consumable_state.filter_left.total_seconds()
                    / 3600)})
            if self.vacuum_state.got_error:
                attrs[ATTR_ERROR] = self.vacuum_state.error
        return attrs

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
        from miio import DeviceException
        try:
            yield from self.hass.async_add_job(partial(func, *args, **kwargs))
            return True
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        is_on = yield from self._try_command(
            "Unable to start the vacuum: %s", self._vacuum.start)
        self._is_on = is_on

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        yield from self.async_stop()
        yield from self.async_return_to_base()

    @asyncio.coroutine
    def async_stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        stopped = yield from self._try_command(
            "Unable to stop: %s", self._vacuum.stop)
        if stopped:
            self._is_on = False

    @asyncio.coroutine
    def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        if fan_speed.capitalize() in FAN_SPEEDS:
            fan_speed = FAN_SPEEDS[fan_speed.capitalize()]
        else:
            try:
                fan_speed = int(fan_speed)
            except ValueError as exc:
                _LOGGER.error("Fan speed step not recognized (%s). "
                              "Valid speeds are: %s", exc,
                              self.fan_speed_list)
                return
        yield from self._try_command(
            "Unable to set fan speed: %s",
            self._vacuum.set_fan_speed, fan_speed)

    @asyncio.coroutine
    def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        if self.vacuum_state and self.is_on:
            yield from self._try_command(
                "Unable to set start/pause: %s", self._vacuum.pause)
        else:
            yield from self.async_turn_on()

    @asyncio.coroutine
    def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        return_home = yield from self._try_command(
            "Unable to return home: %s", self._vacuum.home)
        if return_home:
            self._is_on = False

    @asyncio.coroutine
    def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        yield from self._try_command(
            "Unable to start the vacuum for a spot clean-up: %s",
            self._vacuum.spot)

    @asyncio.coroutine
    def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        yield from self._try_command(
            "Unable to locate the botvac: %s", self._vacuum.find)

    @asyncio.coroutine
    def async_send_command(self, command, params=None, **kwargs):
        """Send raw command."""
        yield from self._try_command(
            "Unable to send command to the vacuum: %s",
            self._vacuum.raw_command, command, params)

    @asyncio.coroutine
    def async_remote_control_start(self):
        """Start remote control mode."""
        yield from self._try_command(
            "Unable to start remote control the vacuum: %s",
            self._vacuum.manual_start)

    @asyncio.coroutine
    def async_remote_control_stop(self):
        """Stop remote control mode."""
        yield from self._try_command(
            "Unable to stop remote control the vacuum: %s",
            self._vacuum.manual_stop)

    @asyncio.coroutine
    def async_remote_control_move(self,
                                  rotation: int=0,
                                  velocity: float=0.3,
                                  duration: int=1500):
        """Move vacuum with remote control mode."""
        yield from self._try_command(
            "Unable to move with remote control the vacuum: %s",
            self._vacuum.manual_control,
            velocity=velocity, rotation=rotation, duration=duration)

    @asyncio.coroutine
    def async_remote_control_move_step(self,
                                       rotation: int=0,
                                       velocity: float=0.2,
                                       duration: int=1500):
        """Move vacuum one step with remote control mode."""
        yield from self._try_command(
            "Unable to remote control the vacuum: %s",
            self._vacuum.manual_control_once,
            velocity=velocity, rotation=rotation, duration=duration)

    def update(self):
        """Fetch state from the device."""
        from miio import DeviceException
        try:
            state = self._vacuum.status()
            self.vacuum_state = state

            self.consumable_state = self._vacuum.consumable_status()
            self.clean_history = self._vacuum.clean_history()
            self.dnd_state = self._vacuum.dnd_status()

            self._is_on = state.is_on
            self._available = True
        except OSError as exc:
            _LOGGER.error("Got OSError while fetching the state: %s", exc)
        except DeviceException as exc:
            _LOGGER.warning("Got exception while fetching the state: %s", exc)
