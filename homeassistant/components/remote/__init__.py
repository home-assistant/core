"""
Component to interface with univeral remote control devices.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/remote/
"""
from datetime import timedelta
import logging
import os

import voluptuous as vol
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import ToggleEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID)
from homeassistant.components import group
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA

ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_ACTIVITY = 'activity'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SYNC = 'sync'
ATTR_DEFAULT = ''

DOMAIN = 'remote'
SCAN_INTERVAL = 30

GROUP_NAME_ALL_REMOTES = 'all remotes'
ENTITY_ID_ALL_REMOTES = group.ENTITY_ID_FORMAT.format('all_remotes')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

REMOTE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_DEVICE): cv.string,
    vol.Optional(ATTR_COMMAND): cv.string,
    vol.Optional(ATTR_ACTIVITY): cv.string
})

_LOGGER = logging.getLogger(__name__)


def is_on(hass, entity_id=None):
    """Return if the remote is on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_REMOTES
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, activity=None, entity_id=None):
    """Turn all or specified remote on."""
    data = {}
    data[ATTR_ACTIVITY] = activity
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """Turn all or specified remote off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def send_command(hass, device=None, command=None, entity_id=None):
    """Send a command to a device"""
    data = {}
    data[ATTR_DEVICE] = str(device)
    data[ATTR_COMMAND] = command
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id
    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)


def sync(hass, entity_id=None):
    """Sync remote device"""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_SYNC, data)


def setup(hass, config):
    """Track states and offer events for remotes."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_REMOTES)
    component.setup(config)

    def handle_remote_service(service):
        """Handle calls to the remote services."""
        target_remotes = component.extract_from_service(service)

        activity_id = service.data.get(ATTR_ACTIVITY, ATTR_DEFAULT)
        device = str(service.data.get(ATTR_DEVICE, ATTR_DEFAULT))
        command = str(service.data.get(ATTR_COMMAND, ATTR_DEFAULT))

        for remote in target_remotes:
            if service.service == SERVICE_TURN_ON:
                remote.turn_on(activity=activity_id)
            elif service.service == SERVICE_SEND_COMMAND:
                remote.send_command(device=device, command=command)
            elif service.service == SERVICE_SYNC:
                remote.sync()
            else:
                remote.turn_off()

            if remote.should_poll:
                remote.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_remote_service,
                           descriptions.get(SERVICE_TURN_OFF),
                           schema=REMOTE_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_remote_service,
                           descriptions.get(SERVICE_TURN_ON),
                           schema=REMOTE_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, handle_remote_service,
                           descriptions.get(SERVICE_SEND_COMMAND),
                           schema=REMOTE_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SYNC, handle_remote_service,
                           descriptions.get(SERVICE_SYNC),
                           schema=REMOTE_SERVICE_SCHEMA)

    return True


class RemoteDevice(ToggleEntity):
    """Representation of a remote."""

    # pylint: disable=no-self-use, abstract-method
    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        data = {}
        return data

    def state(self):
        return self.is_on

    def turn_on(self, **kwargs):
        """Turn a device one with the remote"""
        raise NotImplementedError()

    def turn_off(self, **kwargs):
        """Turn a device off with the remote."""
        raise NotImplementedError()

    def sync(self, **kwargs):
        """Turn a device off with the remote."""
        raise NotImplementedError()

    def send_command(self, **kwargs):
        """Turn a device off with the remote."""
        raise NotImplementedError()
