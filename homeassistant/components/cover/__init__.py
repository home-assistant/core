"""
Component to interface with covers like blinds, rollershutters or garage doors.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/cover/
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
    ATTR_ENTITY_ID, SERVICE_CLOSE, SERVICE_OPEN, SERVICE_STOP, STATE_CLOSED,
    STATE_OPEN, STATE_UNKNOWN)
from homeassistant.components import group

DOMAIN = 'cover'
SCAN_INTERVAL = 30

GROUP_NAME_ALL_COVERS = 'all covers'
ENTITY_ID_ALL_COVERS = group.ENTITY_ID_FORMAT.format('all_covers')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

COVER_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

_LOGGER = logging.getLogger(__name__)


def is_open(hass, entity_id=None):
    """Return if the cover is fully open based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_COVERS
    return hass.states.is_state(entity_id, STATE_OPEN)


def is_closed(hass, entity_id=None):
    """Return if the cover is fully closed based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_COVERS
    return hass.states.is_state(entity_id, STATE_CLOSED)


def open_cover(hass, entity_id=None):
    """Open all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_OPEN, data)


def close_cover(hass, entity_id=None):
    """Close all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLOSE, data)


def stop_cover(hass, entity_id=None):
    """Stop all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP, data)


def setup(hass, config):
    """Track states and offer events for cover."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_COVERS)
    component.setup(config)

    def handle_cover_service(service):
        """Handle calls to the cover services."""
        target_covers = component.extract_from_service(service)

        for cover in target_covers:
            if service.service == SERVICE_CLOSE:
                cover.close_cover()
            elif service.service == SERVICE_OPEN:
                cover.open_cover()
            elif service.service == SERVICE_STOP:
                cover.stop_cover()
            if cover.should_poll:
                cover.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))
    hass.services.register(DOMAIN, SERVICE_OPEN, handle_cover_service,
                           descriptions.get(SERVICE_OPEN),
                           schema=COVER_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_CLOSE, handle_cover_service,
                           descriptions.get(SERVICE_CLOSE),
                           schema=COVER_SERVICE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_STOP,
                           handle_cover_service,
                           descriptions.get(SERVICE_STOP),
                           schema=COVER_SERVICE_SCHEMA)
    return True


class CoverDevice(Entity):
    """Representation of a cover."""

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return None

    @property
    def state(self):
        """Return the state of the cover."""
        closed = self.is_closed

        if closed is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if closed else STATE_OPEN

    def open_cover(self):
        """Fully open the cover."""
        raise NotImplementedError()

    def close_cover(self):
        """Fully close the cover."""
        raise NotImplementedError()

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        raise NotImplementedError()
