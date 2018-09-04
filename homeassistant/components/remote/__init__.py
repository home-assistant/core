"""
Component to interface with universal remote control devices.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/remote/
"""
import asyncio
from datetime import timedelta
import functools as ft
import logging

import voluptuous as vol

from homeassistant.loader import bind_hass
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE,
    ATTR_ENTITY_ID)
from homeassistant.components import group
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa

_LOGGER = logging.getLogger(__name__)

ATTR_ACTIVITY = 'activity'
ATTR_COMMAND = 'command'
ATTR_DEVICE = 'device'
ATTR_NUM_REPEATS = 'num_repeats'
ATTR_DELAY_SECS = 'delay_secs'

DOMAIN = 'remote'
DEPENDENCIES = ['group']
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_ALL_REMOTES = group.ENTITY_ID_FORMAT.format('all_remotes')
ENTITY_ID_FORMAT = DOMAIN + '.{}'

GROUP_NAME_ALL_REMOTES = 'all remotes'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SYNC = 'sync'

DEFAULT_NUM_REPEATS = 1
DEFAULT_DELAY_SECS = 0.4

REMOTE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

REMOTE_SERVICE_ACTIVITY_SCHEMA = REMOTE_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_ACTIVITY): cv.string
})

REMOTE_SERVICE_SEND_COMMAND_SCHEMA = REMOTE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_DEVICE): cv.string,
    vol.Optional(
        ATTR_NUM_REPEATS, default=DEFAULT_NUM_REPEATS): cv.positive_int,
    vol.Optional(ATTR_DELAY_SECS): vol.Coerce(float),
})


@bind_hass
def is_on(hass, entity_id=None):
    """Return if the remote is on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_REMOTES
    return hass.states.is_state(entity_id, STATE_ON)


@bind_hass
def turn_on(hass, activity=None, entity_id=None):
    """Turn all or specified remote on."""
    data = {
        key: value for key, value in [
            (ATTR_ACTIVITY, activity),
            (ATTR_ENTITY_ID, entity_id),
        ] if value is not None}
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


@bind_hass
def turn_off(hass, activity=None, entity_id=None):
    """Turn all or specified remote off."""
    data = {}
    if activity:
        data[ATTR_ACTIVITY] = activity

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


@bind_hass
def toggle(hass, activity=None, entity_id=None):
    """Toggle all or specified remote."""
    data = {}
    if activity:
        data[ATTR_ACTIVITY] = activity

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(DOMAIN, SERVICE_TOGGLE, data)


@bind_hass
def send_command(hass, command, entity_id=None, device=None,
                 num_repeats=None, delay_secs=None):
    """Send a command to a device."""
    data = {ATTR_COMMAND: command}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if device:
        data[ATTR_DEVICE] = device

    if num_repeats:
        data[ATTR_NUM_REPEATS] = num_repeats

    if delay_secs:
        data[ATTR_DELAY_SECS] = delay_secs

    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for remotes."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_REMOTES)
    yield from component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_OFF, REMOTE_SERVICE_ACTIVITY_SCHEMA,
        'async_turn_off'
    )

    component.async_register_entity_service(
        SERVICE_TURN_ON, REMOTE_SERVICE_ACTIVITY_SCHEMA,
        'async_turn_on'
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, REMOTE_SERVICE_ACTIVITY_SCHEMA,
        'async_toggle'
    )

    component.async_register_entity_service(
        SERVICE_SEND_COMMAND, REMOTE_SERVICE_SEND_COMMAND_SCHEMA,
        'async_send_command'
    )

    return True


class RemoteDevice(ToggleEntity):
    """Representation of a remote."""

    def send_command(self, command, **kwargs):
        """Send a command to a device."""
        raise NotImplementedError()

    def async_send_command(self, command, **kwargs):
        """Send a command to a device.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(
            self.send_command, command, **kwargs))
