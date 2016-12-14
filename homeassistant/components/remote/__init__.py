"""
Component to interface with universal remote control devices.

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
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa

_LOGGER = logging.getLogger(__name__)

ATTR_ACTIVITY = 'activity'
ATTR_COMMAND = 'command'
ATTR_DEVICE = 'device'

DOMAIN = 'remote'

ENTITY_ID_ALL_REMOTES = group.ENTITY_ID_FORMAT.format('all_remotes')
ENTITY_ID_FORMAT = DOMAIN + '.{}'

GROUP_NAME_ALL_REMOTES = 'all remotes'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SCAN_INTERVAL = 30
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SYNC = 'sync'

REMOTE_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})

REMOTE_SERVICE_TURN_ON_SCHEMA = REMOTE_SERVICE_SCHEMA.extend({
    vol.Optional(ATTR_ACTIVITY): cv.string
})

REMOTE_SERVICE_SEND_COMMAND_SCHEMA = REMOTE_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_DEVICE): cv.string,
    vol.Required(ATTR_COMMAND): cv.string,
})


def is_on(hass, entity_id=None):
    """Return if the remote is on based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_REMOTES
    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, activity=None, entity_id=None):
    """Turn all or specified remote on."""
    data = {ATTR_ACTIVITY: activity}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id
    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """Turn all or specified remote off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)


def send_command(hass, device, command, entity_id=None):
    """Send a command to a device."""
    data = {ATTR_DEVICE: str(device), ATTR_COMMAND: command}
    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id
    hass.services.call(DOMAIN, SERVICE_SEND_COMMAND, data)


def sync(hass, entity_id=None):
    """Sync remote device."""
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

        activity_id = service.data.get(ATTR_ACTIVITY)
        device = service.data.get(ATTR_DEVICE)
        command = service.data.get(ATTR_COMMAND)

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
                           schema=REMOTE_SERVICE_TURN_ON_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, handle_remote_service,
                           descriptions.get(SERVICE_SEND_COMMAND),
                           schema=REMOTE_SERVICE_SEND_COMMAND_SCHEMA)

    return True


class RemoteDevice(ToggleEntity):
    """Representation of a remote."""

    def turn_on(self, **kwargs):
        """Turn a device on with the remote."""
        raise NotImplementedError()

    def turn_off(self, **kwargs):
        """Turn a device off with the remote."""
        raise NotImplementedError()

    def send_command(self, **kwargs):
        """Send a command to a device."""
        raise NotImplementedError()
