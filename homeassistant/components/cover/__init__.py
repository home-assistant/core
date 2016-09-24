"""
Support for Cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover/
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
    SERVICE_OPEN_COVER, SERVICE_CLOSE_COVER, SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER, SERVICE_OPEN_COVER_TILT, SERVICE_CLOSE_COVER_TILT,
    SERVICE_STOP_COVER_TILT, SERVICE_SET_COVER_TILT_POSITION, STATE_OPEN,
    STATE_CLOSED, STATE_UNKNOWN, ATTR_ENTITY_ID)


DOMAIN = 'cover'
SCAN_INTERVAL = 15

GROUP_NAME_ALL_COVERS = 'all covers'
ENTITY_ID_ALL_COVERS = group.ENTITY_ID_FORMAT.format('all_covers')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

_LOGGER = logging.getLogger(__name__)

ATTR_CURRENT_POSITION = 'current_position'
ATTR_CURRENT_TILT_POSITION = 'current_tilt_position'
ATTR_POSITION = 'position'
ATTR_TILT_POSITION = 'tilt_position'

COVER_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

COVER_SET_COVER_POSITION_SCHEMA = COVER_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_POSITION):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

COVER_SET_COVER_TILT_POSITION_SCHEMA = COVER_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_TILT_POSITION):
        vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
})

SERVICE_TO_METHOD = {
    SERVICE_OPEN_COVER: {'method': 'open_cover'},
    SERVICE_CLOSE_COVER: {'method': 'close_cover'},
    SERVICE_SET_COVER_POSITION: {
        'method': 'set_cover_position',
        'schema': COVER_SET_COVER_POSITION_SCHEMA},
    SERVICE_STOP_COVER: {'method': 'stop_cover'},
    SERVICE_OPEN_COVER_TILT: {'method': 'open_cover_tilt'},
    SERVICE_CLOSE_COVER_TILT: {'method': 'close_cover_tilt'},
    SERVICE_STOP_COVER_TILT: {'method': 'stop_cover_tilt'},
    SERVICE_SET_COVER_TILT_POSITION: {
        'method': 'set_cover_tilt_position',
        'schema': COVER_SET_COVER_TILT_POSITION_SCHEMA},
}


def is_closed(hass, entity_id=None):
    """Return if the cover is closed based on the statemachine."""
    entity_id = entity_id or ENTITY_ID_ALL_COVERS
    return hass.states.is_state(entity_id, STATE_CLOSED)


def open_cover(hass, entity_id=None):
    """Open all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_OPEN_COVER, data)


def close_cover(hass, entity_id=None):
    """Close all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLOSE_COVER, data)


def set_cover_position(hass, position, entity_id=None):
    """Move to specific position all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_POSITION] = position
    hass.services.call(DOMAIN, SERVICE_SET_COVER_POSITION, data)


def stop_cover(hass, entity_id=None):
    """Stop all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP_COVER, data)


def open_cover_tilt(hass, entity_id=None):
    """Open all or specified cover tilt."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_OPEN_COVER_TILT, data)


def close_cover_tilt(hass, entity_id=None):
    """Close all or specified cover tilt."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_CLOSE_COVER_TILT, data)


def set_cover_tilt_position(hass, tilt_position, entity_id=None):
    """Move to specific tilt position all or specified cover."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data[ATTR_TILT_POSITION] = tilt_position
    hass.services.call(DOMAIN, SERVICE_SET_COVER_TILT_POSITION, data)


def stop_cover_tilt(hass, entity_id=None):
    """Stop all or specified cover tilt."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None
    hass.services.call(DOMAIN, SERVICE_STOP_COVER_TILT, data)


def setup(hass, config):
    """Track states and offer events for covers."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_COVERS)
    component.setup(config)

    def handle_cover_service(service):
        """Handle calls to the cover services."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        if method:
            for cover in component.extract_from_service(service):
                getattr(cover, method['method'])(**params)

                if cover.should_poll:
                    cover.update_ha_state(True)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    for service_name in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service_name].get(
            'schema', COVER_SERVICE_SCHEMA)
        hass.services.register(DOMAIN, service_name, handle_cover_service,
                               descriptions.get(service_name), schema=schema)
    return True


class CoverDevice(Entity):
    """Representation a cover."""

    # pylint: disable=no-self-use
    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        pass

    @property
    def current_cover_tilt_position(self):
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        pass

    @property
    def state(self):
        """Return the state of the cover."""
        closed = self.is_closed

        if closed is None:
            return STATE_UNKNOWN

        return STATE_CLOSED if closed else STATE_OPEN

    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}

        current = self.current_cover_position
        if current is not None:
            data[ATTR_CURRENT_POSITION] = self.current_cover_position

        current_tilt = self.current_cover_tilt_position
        if current_tilt is not None:
            data[ATTR_CURRENT_TILT_POSITION] = self.current_cover_tilt_position

        return data

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        raise NotImplementedError()

    def open_cover(self, **kwargs):
        """Open the cover."""
        raise NotImplementedError()

    def close_cover(self, **kwargs):
        """Close cover."""
        raise NotImplementedError()

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        pass

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        pass

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        pass

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        pass

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        pass

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        pass
