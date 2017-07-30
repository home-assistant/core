"""
Support for vacuum cleaner robots (botvacs).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_BATTERY_LEVEL, STATE_UNKNOWN,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.util.icon import icon_for_battery_level

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vacuum'

SCAN_INTERVAL = timedelta(seconds=20)

GROUP_NAME_ALL_VACUUMS = 'all vacuum cleaners'

ATTR_COMMAND = 'command'
ATTR_FANSPEED = 'fanspeed'
ATTR_PARAMS = 'params'

SERVICE_START_PAUSE = 'start_pause'
SERVICE_LOCATE = 'locate'
SERVICE_RETURN_TO_BASE = 'return_to_base'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SET_FANSPEED = 'set_fanspeed'
SERVICE_STOP = 'stop'

VACUUM_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

VACUUM_SET_FANSPEED_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_FANSPEED): cv.string,
})

VACUUM_SEND_COMMAND_SERVICE_SCHEMA = VACUUM_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_PARAMS): vol.Any,
})

SERVICE_TO_METHOD = {
    SERVICE_TURN_ON: {'method': 'async_turn_on'},
    SERVICE_TURN_OFF: {'method': 'async_turn_off'},
    SERVICE_TOGGLE: {'method': 'async_toggle'},
    SERVICE_START_PAUSE: {'method': 'async_start_pause'},
    SERVICE_RETURN_TO_BASE: {'method': 'async_return_to_base'},
    SERVICE_LOCATE: {'method': 'async_locate'},
    SERVICE_STOP: {'method': 'async_stop'},
    SERVICE_SET_FANSPEED: {'method': 'async_set_fanspeed',
                           'schema': VACUUM_SET_FANSPEED_SERVICE_SCHEMA},
    SERVICE_SEND_COMMAND: {'method': 'async_send_command',
                           'schema': VACUUM_SEND_COMMAND_SERVICE_SCHEMA},
}

DEFAULT_NAME = 'Vacuum cleaner robot'
DEFAULT_ICON = 'mdi:google-circles-group'

SUPPORT_TURN_ON = 1
SUPPORT_TURN_OFF = 2
SUPPORT_PAUSE = 4
SUPPORT_STOP = 8
SUPPORT_RETURN_HOME = 16
SUPPORT_FANSPEED = 32
SUPPORT_BATTERY = 64
SUPPORT_STATUS = 128
SUPPORT_SENDCOMMAND = 256
SUPPORT_LOCATE = 512
SUPPORT_MAP = 1024


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the vacuum component."""
    if not config[DOMAIN]:
        return False

    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_VACUUMS)

    yield from component.async_setup(config)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    @asyncio.coroutine
    def async_handle_vacuum_service(service):
        """Map services to methods on VacuumDevice."""
        method = SERVICE_TO_METHOD.get(service.service)
        if not method:
            return

        target_vacuums = component.async_extract_from_service(service)
        params = dict(service.data)
        _LOGGER.debug('Service call to %s: %s (%s)',
                      target_vacuums, method, params)

        update_tasks = []
        for vacuum in target_vacuums:
            yield from getattr(vacuum, method['method'])(**params)
            if not vacuum.should_poll:
                continue

            update_coro = hass.async_add_job(
                vacuum.async_update_ha_state(True))
            if hasattr(vacuum, 'async_update'):
                update_tasks.append(update_coro)
            else:
                yield from update_coro

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service].get(
            'schema', VACUUM_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, service, async_handle_vacuum_service,
            descriptions.get(service), schema=schema)

    return True


class VacuumDevice(ToggleEntity):
    """Representation of a vacuum cleaner robot."""

    @property
    def supported_features(self):
        """Flag vacuum cleaner features that are supported."""
        return 0

    @property
    def state(self):
        """State of the vacuum cleaner."""
        return STATE_UNKNOWN

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
    def fanspeed(self):
        """Return the fan speed of the vacuum cleaner."""
        return None

    @property
    def fanspeed_list(self) -> list:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return []

    @property
    def state_attributes(self):
        """Return the state attributes of the vacuum cleaner."""
        data = {}

        if self.status is not None:
            data['status'] = self.status

        if self.battery_level is not None:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_LEVEL + '_icon'] = self.battery_icon

        if self.fanspeed is not None:
            data['fanspeed'] = self.fanspeed
            data['fanspeed_list'] = self.fanspeed_list

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

    def locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        raise NotImplementedError()

    def async_locate(self, **kwargs):
        """Locate the vacuum cleaner.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.locate, **kwargs))

    def set_fanspeed(self, **kwargs):
        """Set the fanspeed."""
        raise NotImplementedError()

    def async_set_fanspeed(self, **kwargs):
        """Set the fanspeed.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.set_fanspeed, **kwargs))

    def start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task."""
        raise NotImplementedError()

    def async_start_pause(self, **kwargs):
        """Start, pause or resume the cleaning task.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            partial(self.start_pause, **kwargs))

    def send_command(self, **kwargs):
        """Send a command to a vacuum cleaner."""
        raise NotImplementedError()

    def async_send_command(self, **kwargs):
        """Send a command to a vacuum cleaner.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(partial(self.send_command, **kwargs))
