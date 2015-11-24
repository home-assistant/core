"""
homeassistant.components.rollershutter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Rollershutter component.

"""
import os
import logging

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.components import group
from homeassistant.const import (
    SERVICE_MOVE_UP, SERVICE_MOVE_DOWN, SERVICE_MOVE_STOP,
    STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN, ATTR_ENTITY_ID)


DOMAIN = 'rollershutter'
DEPENDENCIES = []
SCAN_INTERVAL = 15

GROUP_NAME_ALL_ROLLERSHUTTERS = 'all rollershutters'
ENTITY_ID_ALL_ROLLERSHUTTERS = group.ENTITY_ID_FORMAT.format(
    'all_rollershutters')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {}

_LOGGER = logging.getLogger(__name__)


def is_open(hass, entity_id=None):
    """ Returns if the rollershutter is open based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_ROLLERSHUTTERS
    return hass.states.is_state(entity_id, STATE_OPEN)


def move_up(hass, entity_id=None):
    """ Moves all or specified rollershutter up. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_MOVE_UP, data)


def move_down(hass, entity_id=None):
    """ Moves all or specified rollershutter down. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_MOVE_DOWN, data)


def move_stop(hass, entity_id=None):
    """ Stops all or specified rollershutter. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_MOVE_STOP, data)


def setup(hass, config):
    """ Track states and offer events for rollershutters. """
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_ROLLERSHUTTERS)
    component.setup(config)

    def handle_rollershutter_service(service):
        """ Handles calls to the rollershutter services. """
        target_rollershutters = component.extract_from_service(service)

        for rollershutter in target_rollershutters:
            if service.service == SERVICE_MOVE_UP:
                rollershutter.move_up()
            elif service.service == SERVICE_MOVE_DOWN:
                rollershutter.move_down()
            elif service.service == SERVICE_MOVE_STOP:
                rollershutter.move_stop()

            if rollershutter.should_poll:
                rollershutter.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_MOVE_UP,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_MOVE_UP))
    hass.services.register(DOMAIN, SERVICE_MOVE_DOWN,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_MOVE_DOWN))
    hass.services.register(DOMAIN, SERVICE_MOVE_STOP,
                           handle_rollershutter_service,
                           descriptions.get(SERVICE_MOVE_STOP))

    return True


class RollershutterDevice(Entity):
    """ Represents a rollershutter within Home Assistant. """
    # pylint: disable=no-self-use

    @property
    def current_position(self):
        """ Return current position of rollershutter.
        None is unknown, 0 is closed, 100 is fully open. """
        raise NotImplementedError()

    @property
    def state(self):
        current = self.current_position

        if current is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if current == 0 else STATE_OPEN

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return None

    def move_up(self, **kwargs):
        """ Moves the device UP. """
        raise NotImplementedError()

    def move_down(self, **kwargs):
        """ Moves the device DOWN. """
        raise NotImplementedError()

    def move_stop(self, **kwargs):
        """ Moves the device to STOP. """
        raise NotImplementedError()
