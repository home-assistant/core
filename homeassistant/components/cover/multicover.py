"""
Support for multiple covers which integrate with other components.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.multicover/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import (callback, split_entity_id)
from homeassistant.components.cover import (
    ENTITY_ID_FORMAT, DOMAIN, PLATFORM_SCHEMA, CoverDevice,
    ATTR_POSITION, ATTR_TILT_POSITION, ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION, SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP,
    SUPPORT_SET_POSITION, SUPPORT_OPEN_TILT, SUPPORT_CLOSE_TILT,
    SUPPORT_STOP_TILT, SUPPORT_SET_TILT_POSITION)
from homeassistant.const import (
    CONF_COVERS, CONF_ENTITY_ID, CONF_FRIENDLY_NAME,
    STATE_CLOSED, ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER, SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER, SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION, SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER, SERVICE_STOP_COVER_TILT)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

COVER_FEATURES = SUPPORT_OPEN | SUPPORT_CLOSE | \
                 SUPPORT_STOP | SUPPORT_SET_POSITION
TILT_FEATURES = SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | \
                SUPPORT_STOP_TILT | SUPPORT_SET_TILT_POSITION


CONF_TILT = 'tilt'

KEY_OPEN_CLOSE = 'open_close'
KEY_STOP = 'stop'
KEY_POSITION = 'position'


COVER_SCHEMA = vol.Schema({
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_TILT, default=False): cv.boolean,
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_COVERS): vol.Schema({cv.slug: COVER_SCHEMA}),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the MultiCover."""
    covers = []

    for device, device_config in config[CONF_COVERS].items():
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        tilt = device_config.get(CONF_TILT)
        entity_ids = device_config.get(CONF_ENTITY_ID)

        covers.append(
            MultiCover(hass, device, friendly_name, tilt, entity_ids))

    if not covers:
        _LOGGER.error("No multicovers added.")
        return False

    async_add_devices(covers, True)
    return True


class MultiCover(CoverDevice):
    """Representation of a MultiCover."""

    def __init__(self, hass, device_id, friendly_name, tilt, entity_ids):
        """Initialize a multicover entity."""
        self._hass = hass
        self._device_id = device_id
        self._name = friendly_name
        self._tilt = tilt
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass)
        self.entities = self.get_entities_set(entity_ids)
        self.covers = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                       KEY_POSITION: set()}
        self.tilts = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                      KEY_POSITION: set()}

    def get_entities_set(self, entity_ids):
        """Check if entities are valid."""
        entities = set()
        for entity in entity_ids:
            if split_entity_id(entity)[0] != DOMAIN:
                _LOGGER.warning("%s: Only cover entities are allowed. Please "
                                "remove: \"%s\".", self._device_id, entity)
                continue
            if entity == self.entity_id:
                _LOGGER.warning("%s: The entity_id of this component \"%s\" "
                                "is not allowed.", self._device_id, entity)
                continue
            entities.add(entity)
        return entities

    def update_supported_features(self, entity_id, old_state, new_state):
        """Update dictionaries with supported features."""
        if new_state is None:
            for value in self.covers.values():
                value.discard(entity_id)
            for value in self.tilts.values():
                value.discard(entity_id)
            return

        if old_state is None:
            features = new_state.attributes[ATTR_SUPPORTED_FEATURES]
            if features & 1 and features & 2:
                self.covers[KEY_OPEN_CLOSE].add(entity_id)
            if features & 4:
                self.covers[KEY_POSITION].add(entity_id)
            if features & 8:
                self.covers[KEY_STOP].add(entity_id)
            if features & 16 and features & 32:
                self.tilts[KEY_OPEN_CLOSE].add(entity_id)
            if features & 64:
                self.tilts[KEY_STOP].add(entity_id)
            if features & 128:
                self.tilts[KEY_POSITION].add(entity_id)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def state_change_listener(entity, old_state, new_state):
            """Handle cover state changes and update state."""
            self.update_supported_features(entity, old_state, new_state)
            self.async_schedule_update_ha_state(True)

        for entity_id in self.entities:
            new_state = self._hass.states.get(entity_id)
            self.update_supported_features(entity_id, None, new_state)
        async_track_state_change(self._hass, self.entities,
                                 state_change_listener)

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def assumed_state(self):
        """Enable buttons even if at end position."""
        return True

    @property
    def should_poll(self):
        """Disable polling for the MultiCover."""
        return False

    @property
    def is_closed(self):
        """Return if all covers in group are closed."""
        if self.covers[KEY_OPEN_CLOSE] == set():
            return False
        for entity_id in self.covers[KEY_OPEN_CLOSE]:
            state = self._hass.states.get(entity_id)
            if state is None or state.state != STATE_CLOSED:
                return False
        return True

    @property
    def current_cover_position(self):
        """Return current position for all covers.

        None is unknown. pos if all have the same position.
        Else 0 if closed or 100 is fully open.
        """
        position = -1
        for entity_id in self.covers[KEY_POSITION]:
            state = self._hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position

        return 0 if self.is_closed else 100

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position for all covers.

        None is unknown. pos if all have the same tilt position.
        Else 100 for tilt open.
        """
        if self._tilt is False:
            return None

        position = -1
        for entity_id in self.tilts[KEY_POSITION]:
            state = self._hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position

        return 100

    @property
    def state_attributes(self):
        """Return the current position as attribute."""
        data = {}
        current_cover = self.current_cover_position
        current_tilt = self.current_cover_tilt_position
        if current_cover is not None:
            data[ATTR_CURRENT_POSITION] = current_cover
        if current_tilt is not None:
            data[ATTR_CURRENT_TILT_POSITION] = current_tilt
        return data

    @property
    def supported_features(self):
        """Flag supported features for a cover."""
        if not self._tilt:
            return COVER_FEATURES

        return COVER_FEATURES | TILT_FEATURES

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Move the covers up."""
        _LOGGER.debug("Open covers called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER,
            {'entity_id': self.covers[KEY_OPEN_CLOSE]}))

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Move the covers down."""
        _LOGGER.debug("Close covers called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER,
            {'entity_id': self.covers[KEY_OPEN_CLOSE]}))

    @asyncio.coroutine
    def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        _LOGGER.debug("Stop covers called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER,
            {'entity_id': self.covers[KEY_STOP]}))

    @asyncio.coroutine
    def async_set_cover_position(self, **kwargs):
        """Set covers position."""
        position = kwargs[ATTR_POSITION]
        _LOGGER.debug("Set cover position called: %d", position)
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_SET_COVER_POSITION,
            {'entity_id': self.covers[KEY_POSITION],
             ATTR_POSITION: position}))

    @asyncio.coroutine
    def async_open_cover_tilt(self, **kwargs):
        """Tilt covers open."""
        _LOGGER.debug("Open tilts called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER_TILT,
            {'entity_id': self.tilts[KEY_OPEN_CLOSE]}))

    @asyncio.coroutine
    def async_close_cover_tilt(self, **kwargs):
        """Tilt covers closed."""
        _LOGGER.debug("Close tilts called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER_TILT,
            {'entity_id': self.tilts[KEY_OPEN_CLOSE]}))

    @asyncio.coroutine
    def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        _LOGGER.debug("Stop tilts called")
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER_TILT,
            {'entity_id': self.tilts[KEY_STOP]}))

    @asyncio.coroutine
    def async_set_cover_tilt_position(self, **kwargs):
        """Set tilt position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        _LOGGER.debug("Set tilt position called: %d", tilt_position)
        self._hass.add_job(self._hass.services.async_call(
            DOMAIN, SERVICE_SET_COVER_TILT_POSITION,
            {'entity_id': self.tilts[KEY_POSITION],
             ATTR_TILT_POSITION: tilt_position}))
