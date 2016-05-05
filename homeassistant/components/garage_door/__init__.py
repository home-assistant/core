"""
Component to interface with garage doors that can be controlled remotely.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/garage_door/
"""
import logging
import os

import voluptuous as vol

from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    STATE_CLOSED, STATE_OPEN, STATE_UNKNOWN, SERVICE_CLOSE, SERVICE_OPEN,
    ATTR_ENTITY_ID)
from homeassistant.components import (group, wink)

DOMAIN = 'garage_door'
SCAN_INTERVAL = 30

GROUP_NAME_ALL_GARAGE_DOORS = 'all garage doors'
ENTITY_ID_ALL_GARAGE_DOORS = group.ENTITY_ID_FORMAT.format('all_garage_doors')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    wink.DISCOVER_GARAGE_DOORS: 'wink'
}

GARAGE_DOOR_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

_LOGGER = logging.getLogger(__name__)


def is_closed(hass, entity_id=None):
    """Return if the garage door is closed based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_GARAGE_DOORS
    return hass.states.is_state(entity_id, STATE_CLOSED)


def close_door(hass, entity_id=None):
    """Close all or a specified garage door."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLOSE, data)


def open_door(hass, entity_id=None):
    """Open all or specified garage door."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_OPEN, data)


def setup(hass, config):
    """Track states and offer events for garage door."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, DISCOVERY_PLATFORMS,
        GROUP_NAME_ALL_GARAGE_DOORS)
    component.setup(config)

    def handle_garage_door_service(service):
        """Handle calls to the garage door services."""
        target_locks = component.extract_from_service(service)

        for item in target_locks:
            if service.service == SERVICE_CLOSE:
                item.close_door()
            else:
                item.open_door()

            if item.should_poll:
                item.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_OPEN, handle_garage_door_service,
                           descriptions.get(SERVICE_OPEN),
                           schema=GARAGE_DOOR_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_CLOSE, handle_garage_door_service,
                           descriptions.get(SERVICE_CLOSE),
                           schema=GARAGE_DOOR_SERVICE_SCHEMA)
    return True


class GarageDoorDevice(Entity):
    """Representation of a garage door."""

    # pylint: disable=no-self-use
    @property
    def is_closed(self):
        """Return true if door is closed."""
        return None

    def close_door(self):
        """Close the garage door."""
        raise NotImplementedError()

    def open_door(self):
        """Open the garage door."""
        raise NotImplementedError()

    @property
    def state(self):
        """Return the state of the garage door."""
        closed = self.is_closed
        if closed is None:
            return STATE_UNKNOWN
        return STATE_CLOSED if closed else STATE_OPEN
