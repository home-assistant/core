"""
Support for Roller shutters.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter/
"""
import os
import logging

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.components import group
from homeassistant.const import (
    SERVICE_MOVE_UP, SERVICE_MOVE_DOWN, SERVICE_STOP,
    STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN, ATTR_ENTITY_ID)


DOMAIN = 'rollershutter'
SCAN_INTERVAL = 15

GROUP_NAME_ALL_ROLLERSHUTTERS = 'all rollershutters'
ENTITY_ID_ALL_ROLLERSHUTTERS = group.ENTITY_ID_FORMAT.format(
    'all_rollershutters')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POSITION = 'current_position'

ROLLERSHUTTER_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def is_open(hass, entity_id=None):
    """Return if the roller shutter is open based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_ROLLERSHUTTERS
    return hass.states.is_state(entity_id, STATE_OPEN)


def move_up(hass, entity_id=None):
    """Move up all or specified roller shutter."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_MOVE_UP, data)


def move_down(hass, entity_id=None):
    """Move down all or specified roller shutter."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_MOVE_DOWN, data)


def stop(hass, entity_id=None):
    """Stop all or specified roller shutter."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP, data)


def setup(hass, config):
    """Track states and offer events for roller shutters."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_ROLLERSHUTTERS)
    component.setup(config)

    def handle_rollershutter_service(service):
        """Handle calls to the roller shutter services."""
        target_rollershutters = component.extract_from_service(service)

        for rollershutter in target_rollershutters:
            if service.service == SERVICE_MOVE_UP:
                rollershutter.move_up()
            elif service.service == SERVICE_MOVE_DOWN:
                rollershutter.move_down()
            elif service.service == SERVICE_STOP:
                rollershutter.stop()

            if rollershutter.should_poll:
                rollershutter.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_MOVE_UP,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_MOVE_UP),
                           schema=ROLLERSHUTTER_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_MOVE_DOWN,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_MOVE_DOWN),
                           schema=ROLLERSHUTTER_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_STOP,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_STOP),
                           schema=ROLLERSHUTTER_SERVICE_SCHEMA)
    return True


class RollershutterDevice(Entity):
    """Representation a rollers hutter."""

    # pylint: disable=no-self-use
    @property
    def current_position(self):
        """Return current position of roller shutter.

        None is unknown, 0 is closed, 100 is fully open.
        """
        raise NotImplementedError()

    @property
    def state(self):
        """Return the state of the roller shutter."""
        current = self.current_position

        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 0 else STATE_OPEN

    @property
    def state_attributes(self):
        """Return the state attributes."""
        current = self.current_position

        if current is None:
            return None

        return {
            ATTR_CURRENT_POSITION: current
        }

    def move_up(self, **kwargs):
        """Move the roller shutter down."""
        raise NotImplementedError()

    def move_down(self, **kwargs):
        """Move the roller shutter up."""
        raise NotImplementedError()

    def stop(self, **kwargs):
        """Stop the roller shutter."""
        raise NotImplementedError()
