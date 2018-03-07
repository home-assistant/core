"""
This platform allows several cover to be grouped into one cover.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.group/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.cover import (
    DOMAIN, PLATFORM_SCHEMA, CoverDevice, ATTR_POSITION,
    ATTR_CURRENT_POSITION, ATTR_TILT_POSITION, ATTR_CURRENT_TILT_POSITION,
    SUPPORT_OPEN, SUPPORT_CLOSE, SUPPORT_STOP, SUPPORT_SET_POSITION,
    SUPPORT_OPEN_TILT, SUPPORT_CLOSE_TILT,
    SUPPORT_STOP_TILT, SUPPORT_SET_TILT_POSITION,
    open_cover, open_cover_tilt, close_cover, close_cover_tilt, stop_cover,
    stop_cover_tilt, set_cover_position, set_cover_tilt_position)
from homeassistant.const import (
    CONF_ENTITIES, CONF_NAME, ATTR_SUPPORTED_FEATURES, STATE_CLOSED)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change

_LOGGER = logging.getLogger(__name__)

TILT_FEATURES = SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | \
                SUPPORT_STOP_TILT | SUPPORT_SET_TILT_POSITION

KEY_OPEN_CLOSE = 'open_close'
KEY_STOP = 'stop'
KEY_POSITION = 'position'

DEFAULT_NAME = 'Cover Group'


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the Group Cover platform."""
    async_add_devices(
        [CoverGroup(config[CONF_NAME], config[CONF_ENTITIES])])


class CoverGroup(CoverDevice):
    """Representation of a CoverGroup."""

    def __init__(self, name, entities):
        """Initialize a CoverGroup entity."""
        self._name = name
        self._tilt = False

        self._is_closed = False
        self._cover_position = 100
        self._tilt_position = None
        self._supported_features = 0

        self._entities = entities
        self._covers = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                        KEY_POSITION: set()}
        self._tilts = {KEY_OPEN_CLOSE: set(), KEY_STOP: set(),
                       KEY_POSITION: set()}

    def update_supported_features(self, entity_id, old_state, new_state):
        """Update dictionaries with supported features."""
        if new_state is None:
            for value in self._covers.values():
                value.discard(entity_id)
            for value in self._tilts.values():
                value.discard(entity_id)
                tilt = True if value else False
            self._tilt = tilt
            return

        if old_state is None:
            features = new_state.attributes[ATTR_SUPPORTED_FEATURES]
            if features & (SUPPORT_OPEN | SUPPORT_CLOSE):
                self._covers[KEY_OPEN_CLOSE].add(entity_id)
            if features & (SUPPORT_STOP):
                self._covers[KEY_STOP].add(entity_id)
            if features & (SUPPORT_SET_POSITION):
                self._covers[KEY_POSITION].add(entity_id)
            if features & (SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT):
                self._tilts[KEY_OPEN_CLOSE].add(entity_id)
                self._tilt = True
            if features & (SUPPORT_STOP_TILT):
                self._tilts[KEY_STOP].add(entity_id)
                self._tilt = True
            if features & (SUPPORT_SET_TILT_POSITION):
                self._tilts[KEY_POSITION].add(entity_id)
                self._tilt = True

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def state_change_listener(entity, old_state, new_state):
            """Handle cover state changes and update state."""
            self.update_supported_features(entity, old_state, new_state)
            self.async_schedule_update_ha_state(True)

        for entity_id in self._entities:
            new_state = self.hass.states.get(entity_id)
            self.update_supported_features(entity_id, None, new_state)
        self.async_schedule_update_ha_state(True)
        async_track_state_change(self.hass, self._entities,
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
        """Disable polling for cover group."""
        return False

    @property
    def supported_features(self):
        """Flag supported features for the cover."""
        return self._supported_features

    @property
    def is_closed(self):
        """Return if all covers in group are closed."""
        return self._is_closed

    @property
    def current_cover_position(self):
        """Return current position for all covers."""
        return self._cover_position

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position for all covers."""
        return self._tilt_position

    async def async_open_cover(self, **kwargs):
        """Move the covers up."""
        self.hass.async_add_job(open_cover, self.hass,
                                self._covers[KEY_OPEN_CLOSE])

    async def async_close_cover(self, **kwargs):
        """Move the covers down."""
        self.hass.async_add_job(close_cover, self.hass,
                                self._covers[KEY_OPEN_CLOSE])

    async def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        self.hass.async_add_job(stop_cover, self.hass,
                                self._covers[KEY_STOP])

    async def async_set_cover_position(self, **kwargs):
        """Set covers position."""
        position = kwargs[ATTR_POSITION]
        self.hass.async_add_job(set_cover_position, self.hass,
                                position, self._covers[KEY_POSITION])

    async def async_open_cover_tilt(self, **kwargs):
        """Tilt covers open."""
        self.hass.async_add_job(open_cover_tilt, self.hass,
                                self._tilts[KEY_OPEN_CLOSE])

    async def async_close_cover_tilt(self, **kwargs):
        """Tilt covers closed."""
        self.hass.async_add_job(close_cover_tilt, self.hass,
                                self._tilts[KEY_OPEN_CLOSE])

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        self.hass.async_add_job(stop_cover_tilt, self.hass,
                                self._tilts[KEY_STOP])

    async def async_set_cover_tilt_position(self, **kwargs):
        """Set tilt position."""
        tilt_position = kwargs[ATTR_TILT_POSITION]
        self.hass.async_add_job(set_cover_tilt_position, self.hass,
                                tilt_position, self._tilts[KEY_POSITION])

    def update_attr_is_closed(self):
        """Return if all covers are closed."""
        if not self._covers[KEY_OPEN_CLOSE]:
            return False
        for entity_id in self._covers[KEY_OPEN_CLOSE]:
            state = self.hass.states.get(entity_id)
            if state is None or state.state != STATE_CLOSED:
                return False
        return True

    def update_attr_cover_position(self):
        """Return current position for all covers.

        None is unknown. pos if all have the same position.
        Else 0 if closed or 100 is fully open.
        """
        position = -1
        for entity_id in self._covers[KEY_POSITION]:
            state = self.hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position

        return 0 if self.is_closed else 100

    def update_attr_tilt_position(self):
        """Return current tilt position for all covers.

        None is unknown. pos if all have the same tilt position.
        Else 100 for tilt open.
        """
        if self._tilt is False:
            return None

        position = -1
        for entity_id in self._tilts[KEY_POSITION]:
            state = self.hass.states.get(entity_id)
            pos = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
            if position == -1:
                position = pos
            elif position != pos:
                position = -1
                break

        if position != -1:
            return position

        return 100

    def update_attr_supported_features(self):
        """Return supported features."""
        supported_features = 0

        if self._covers[KEY_OPEN_CLOSE]:
            supported_features |= SUPPORT_OPEN | SUPPORT_CLOSE

        if self._covers[KEY_STOP]:
            supported_features |= SUPPORT_STOP

        if self._covers[KEY_POSITION]:
            supported_features |= SUPPORT_SET_POSITION

        if self._tilt:
            supported_features |= TILT_FEATURES

        return supported_features

    async def async_update(self):
        """Update state and attributes.

        Update_cover_position must be executed after update_attr_is_closed.
        """
        self._is_closed = self.update_attr_is_closed()
        self._cover_position = self.update_attr_cover_position()
        self._tilt_position = self.update_attr_tilt_position()
        self._supported_features = self.update_attr_supported_features()
