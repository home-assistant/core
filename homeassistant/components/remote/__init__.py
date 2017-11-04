"""
Component to interface with universal remote control devices.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/remote/
"""
import asyncio
from datetime import timedelta
import functools as ft
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
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
    vol.Optional(
        ATTR_DELAY_SECS, default=DEFAULT_DELAY_SECS): vol.Coerce(float)
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

    @asyncio.coroutine
    def async_handle_remote_service(service):
        """Handle calls to the remote services."""
        target_remotes = component.async_extract_from_service(service)

        activity_id = service.data.get(ATTR_ACTIVITY)
        device = service.data.get(ATTR_DEVICE)
        command = service.data.get(ATTR_COMMAND)
        num_repeats = service.data.get(ATTR_NUM_REPEATS)
        delay_secs = service.data.get(ATTR_DELAY_SECS)

        update_tasks = []
        for remote in target_remotes:
            if service.service == SERVICE_TURN_ON:
                yield from remote.async_turn_on(activity=activity_id)
            elif service.service == SERVICE_TOGGLE:
                yield from remote.async_toggle(activity=activity_id)
            elif service.service == SERVICE_SEND_COMMAND:
                yield from remote.async_send_command(
                    device=device, command=command,
                    num_repeats=num_repeats, delay_secs=delay_secs)
            else:
                yield from remote.async_turn_off(activity=activity_id)

            if not remote.should_poll:
                continue
            update_tasks.append(remote.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_OFF, async_handle_remote_service,
        descriptions.get(SERVICE_TURN_OFF),
        schema=REMOTE_SERVICE_ACTIVITY_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TURN_ON, async_handle_remote_service,
        descriptions.get(SERVICE_TURN_ON),
        schema=REMOTE_SERVICE_ACTIVITY_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_TOGGLE, async_handle_remote_service,
        descriptions.get(SERVICE_TOGGLE),
        schema=REMOTE_SERVICE_ACTIVITY_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_COMMAND, async_handle_remote_service,
        descriptions.get(SERVICE_SEND_COMMAND),
        schema=REMOTE_SERVICE_SEND_COMMAND_SCHEMA)

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
