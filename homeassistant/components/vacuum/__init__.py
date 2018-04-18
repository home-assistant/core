"""
Support for vacuum cleaner robots (botvacs).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components import group
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_COMMAND, ATTR_ENTITY_ID, SERVICE_TOGGLE,
    SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_ON)
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vacuum'
DEPENDENCIES = ['group']

SCAN_INTERVAL = timedelta(seconds=20)

GROUP_NAME_ALL_VACUUMS = 'all vacuum cleaners'
ENTITY_ID_ALL_VACUUMS = group.ENTITY_ID_FORMAT.format('all_vacuum_cleaners')

ATTR_BATTERY_ICON = 'battery_icon'
ATTR_CLEANED_AREA = 'cleaned_area'
ATTR_FAN_SPEED = 'fan_speed'
ATTR_FAN_SPEED_LIST = 'fan_speed_list'
ATTR_PARAMS = 'params'
ATTR_STATUS = 'status'

SERVICE_CLEAN_SPOT = 'clean_spot'
SERVICE_LOCATE = 'locate'
SERVICE_RETURN_TO_BASE = 'return_to_base'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SET_FAN_SPEED = 'set_fan_speed'
SERVICE_START_PAUSE = 'start_pause'
SERVICE_STOP = 'stop'

VACUUM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

VACUUM_SET_FAN_SPEED_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FAN_SPEED): cv.string,
})

VACUUM_SEND_COMMAND_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): vol.Any(cv.Dict, cv.ensure_list),
})

SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: {'method': 'async_turn_on'},
    SERVICE_TURN_OFF: {'method': 'async_turn_off'},
    SERVICE_TOGGLE: {'method': 'async_toggle'},
    SERVICE_START_PAUSE: {'method': 'async_start_pause'},
    SERVICE_RETURN_TO_BASE: {'method': 'async_return_to_base'},
    SERVICE_CLEAN_SPOT: {'method': 'async_clean_spot'},
    SERVICE_LOCATE: {'method': 'async_locate'},
    SERVICE_STOP: {'method': 'async_stop'},
    SERVICE_SET_FAN_SPEED: {'method': 'async_set_fan_speed',
                            'schema': VACUUM_SET_FAN_SPEED_SERVICE_SCHEMA},
    SERVICE_SEND_COMMAND: {'method': 'async_send_command',
                           'schema': VACUUM_SEND_COMMAND_SERVICE_SCHEMA},
}

DEFAULT_NAME = 'Vacuum cleaner robot'

SUPPORT_TURN_ON = 1
SUPPORT_TURN_OFF = 2
SUPPORT_PAUSE = 4
SUPPORT_STOP = 8
SUPPORT_RETURN_HOME = 16
SUPPORT_FAN_SPEED = 32
SUPPORT_BATTERY = 64
SUPPORT_STATUS = 128
SUPPORT_SEND_COMMAND = 256
SUPPORT_LOCATE = 512
SUPPORT_CLEAN_SPOT = 1024
SUPPORT_MAP = 2048


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the vacuum is on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_VACUUMS
    return hass.states.is_state(entity_id, STATE_ON)


@bind_hass
def turn_on(hass, entity_id=None):
    """Turn all or specified vacuum on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, entity_id=None):
    """Turn all or specified vacuum off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, entity_id=None):
    """Toggle all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def locate(hass, entity_id=None):
    """Locate all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_LOCATE, data)


@bind_hass
def clean_spot(hass, entity_id=None):
    """Tell all or specified vacuum to perform a spot clean-up."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLEAN_SPOT, data)


@bind_hass
def return_to_base(hass, entity_id=None):
    """Tell all or specified vacuum to return to base."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_RETURN_TO_BASE, data)


@bind_hass
def start_pause(hass, entity_id=None):
    """Tell all or specified vacuum to start or pause the current task."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_START_PAUSE, data)


@bind_hass
def stop(hass, entity_id=None):
    """Stop all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP, data)


@bind_hass
def set_fan_speed(hass, fan_speed, entity_id=None):
    """Set fan speed for all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_FAN_SPEED] = fan_speed
    hass.services.call(DOMAIN, SERVICE_SET_FAN_SPEED, data)


@bind_hass
def send_command(hass, command, params=None, entity_id=None):
    """Send command to all or specified vacuum."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_COMMAND] = command
    if params is not None:
        data[ATTR_PARAMS] = params
    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the vacuum component."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_VACUUMS)

    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_handle_vacuum_service(service):
        """Map services to methods on VacuumDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        target_vacuums = component.async_extract_from_service(service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        update_tasks = []
        for vacuum in target_vacuums:
            yield from getattr(vacuum, method['method'])(**params)
            if not vacuum.should_poll:
                continue
            update_tasks.append(vacuum.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service].get(
            'schema', VACUUM_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, service, async_handle_vacuum_service,
            schema=schema)

    return True


class VacuumDevice(ToggleEntity):
    """Representation of a vacuum cleaner robot."""

    @property
    def supported_features(self):
        """Flag vacuum cleaner features that are supported."""
        raise NotImplementedError()

    @property
    def status(self):
        """Return the status of the vacuum cleaner."""
        return None

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return None

    @property
    def battery_icon(self):
        """Return the battery icon for the vacuum cleaner."""
        charging = False
        if self.status is not None:
            charging = 'charg' in self.status.lower()
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging)

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return None

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        raise NotImplementedError()

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self.status is not None:
            data[ATTR_STATUS] = self.status

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.fan_speed is not None:
            data[ATTR_FAN_SPEED] = self.fan_speed
            data[ATTR_FAN_SPEED_LIST] = self.fan_speed_list

        return data

    def turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning."""
        raise NotImplementedError()

    def async_turn_on(self, **kwargs):
        """Turn the vacuum on and start cleaning.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home."""
        raise NotImplementedError()

    def async_turn_off(self, **kwargs):
        """Turn the vacuum off stopping the cleaning and returning home.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.turn_off, **kwargs))

    def return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        raise NotImplementedError()

    def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.return_to_base, **kwargs))

    def stop(self, **kwargs):
        """Stop the vacuum cleaner."""
        raise NotImplementedError()

    def async_stop(self, **kwargs):
        """Stop the vacuum cleaner.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.stop, **kwargs))

    def clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        raise NotImplementedError()

    def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.clean_spot, **kwargs))

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        raise NotImplementedError()

    def async_locate(self, **kwargs):
        """Locate the vacuum cleaner.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.locate, **kwargs))

    def set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        raise NotImplementedError()

    def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            partial(self.set_fan_speed, fan_speed, **kwargs))

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        raise NotImplementedError()

    def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            partial(self.start_pause, **kwargs))

    def send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner."""
        raise NotImplementedError()

    def async_send_command(self, command, params=None, **kwargs):
        """Send a command to a vacuum cleaner.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            partial(self.send_command, command, params=params, **kwargs))
