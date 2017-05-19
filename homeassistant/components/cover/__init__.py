"""
Support for Cover devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover/
"""
import asyncio
from datetime import timedelta
import functools as ft
import logging
import os

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

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'cover'
SCAN_INTERVAL = timedelta(seconds=15)

GROUP_NAME_ALL_COVERS = 'all covers'
ENTITY_ID_ALL_COVERS = group.ENTITY_ID_FORMAT.format('all_covers')

ENTITY_ID_FORMAT = DOMAIN + '.{}'

DEVICE_CLASSES = [
    'window',        # Window control
    'garage',        # Garage door control
]

SUPPORT_OPEN = 1
SUPPORT_CLOSE = 2
SUPPORT_SET_POSITION = 4
SUPPORT_STOP = 8
SUPPORT_OPEN_TILT = 16
SUPPORT_CLOSE_TILT = 32
SUPPORT_STOP_TILT = 64
SUPPORT_SET_TILT_POSITION = 128

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
    SERVICE_OPEN_COVER: {'method': 'async_open_cover'},
    SERVICE_CLOSE_COVER: {'method': 'async_close_cover'},
    SERVICE_SET_COVER_POSITION: {
        'method': 'async_set_cover_position',
        'schema': COVER_SET_COVER_POSITION_SCHEMA},
    SERVICE_STOP_COVER: {'method': 'async_stop_cover'},
    SERVICE_OPEN_COVER_TILT: {'method': 'async_open_cover_tilt'},
    SERVICE_CLOSE_COVER_TILT: {'method': 'async_close_cover_tilt'},
    SERVICE_STOP_COVER_TILT: {'method': 'async_stop_cover_tilt'},
    SERVICE_SET_COVER_TILT_POSITION: {
        'method': 'async_set_cover_tilt_position',
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


@asyncio.coroutine
def async_setup(hass, config):
    """Track states and offer events for covers."""
    component = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL, GROUP_NAME_ALL_COVERS)

    yield from component.async_setup(config)

    @asyncio.coroutine
    def async_handle_cover_service(service):
        """Handle calls to the cover services."""
        covers = component.async_extract_from_service(service)
        method = SERVICE_TO_METHOD.get(service.service)
        params = service.data.copy()
        params.pop(ATTR_ENTITY_ID, None)

        # call method
        for cover in covers:
            yield from getattr(cover, method['method'])(**params)

        update_tasks = []

        for cover in covers:
            if not cover.should_poll:
                continue

            update_coro = hass.async_add_job(
                cover.async_update_ha_state(True))
            if hasattr(cover, 'async_update'):
                update_tasks.append(update_coro)
            else:
                yield from update_coro

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    descriptions = yield from hass.async_add_job(
        load_yaml_config_file, os.path.join(
            os.path.dirname(__file__), 'services.yaml'))

    for service_name in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[service_name].get(
            'schema', COVER_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, service_name, async_handle_cover_service,
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
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if self.current_cover_position is not None:
            supported_features |= SUPPORT_SET_POSITION

        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_STOP_TILT |
                SUPPORT_SET_TILT_POSITION)

        return supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        raise NotImplementedError()

    def open_cover(self, **kwargs):
        """Open the cover."""
        raise NotImplementedError()

    def async_open_cover(self, **kwargs):
        """Open the cover.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.open_cover, **kwargs))

    def close_cover(self, **kwargs):
        """Close cover."""
        raise NotImplementedError()

    def async_close_cover(self, **kwargs):
        """Close cover.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.close_cover, **kwargs))

    def set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        pass

    def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.set_cover_position, **kwargs))

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        pass

    def async_stop_cover(self, **kwargs):
        """Stop the cover.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.stop_cover, **kwargs))

    def open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        pass

    def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.open_cover_tilt, **kwargs))

    def close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        pass

    def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.close_cover_tilt, **kwargs))

    def set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        pass

    def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.set_cover_tilt_position, **kwargs))

    def stop_cover_tilt(self, **kwargs):
        """Stop the cover."""
        pass

    def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            ft.partial(self.stop_cover_tilt, **kwargs))
