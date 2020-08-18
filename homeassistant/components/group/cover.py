"""This platform allows several cover to be grouped into one cover."""
import logging
from typing import Dict, Optional, Set

import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN,
    PLATFORM_SCHEMA,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.core import State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event

# mypy: allow-incomplete-defs, allow-untyped-calls, allow-untyped-defs
# mypy: no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

KEY_OPEN_CLOSE = "open_close"
KEY_STOP = "stop"
KEY_POSITION = "position"

DEFAULT_NAME = "Cover Group"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Group Cover platform."""
    async_add_entities([CoverGroup(config[CONF_NAME], config[CONF_ENTITIES])])


class CoverGroup(CoverEntity):
    """Representation of a CoverGroup."""

    def __init__(self, name, entities):
        """Initialize a CoverGroup entity."""
        self._name = name
        self._is_closed = False
        self._is_closing = False
        self._is_opening = False
        self._cover_position: Optional[int] = 100
        self._tilt_position = None
        self._supported_features = 0
        self._assumed_state = True

        self._entities = entities
        self._covers: Dict[str, Set[str]] = {
            KEY_OPEN_CLOSE: set(),
            KEY_STOP: set(),
            KEY_POSITION: set(),
        }
        self._tilts: Dict[str, Set[str]] = {
            KEY_OPEN_CLOSE: set(),
            KEY_STOP: set(),
            KEY_POSITION: set(),
        }

    @callback
    def _update_supported_features_event(self, event):
        self.update_supported_features(
            event.data.get("entity_id"), event.data.get("new_state")
        )

    @callback
    def update_supported_features(
        self, entity_id: str, new_state: Optional[State], update_state: bool = True,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._covers.values():
                values.discard(entity_id)
            for values in self._tilts.values():
                values.discard(entity_id)
            if update_state:
                self.async_schedule_update_ha_state(True)
            return

        features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & (SUPPORT_OPEN | SUPPORT_CLOSE):
            self._covers[KEY_OPEN_CLOSE].add(entity_id)
        else:
            self._covers[KEY_OPEN_CLOSE].discard(entity_id)
        if features & (SUPPORT_STOP):
            self._covers[KEY_STOP].add(entity_id)
        else:
            self._covers[KEY_STOP].discard(entity_id)
        if features & (SUPPORT_SET_POSITION):
            self._covers[KEY_POSITION].add(entity_id)
        else:
            self._covers[KEY_POSITION].discard(entity_id)

        if features & (SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT):
            self._tilts[KEY_OPEN_CLOSE].add(entity_id)
        else:
            self._tilts[KEY_OPEN_CLOSE].discard(entity_id)
        if features & (SUPPORT_STOP_TILT):
            self._tilts[KEY_STOP].add(entity_id)
        else:
            self._tilts[KEY_STOP].discard(entity_id)
        if features & (SUPPORT_SET_TILT_POSITION):
            self._tilts[KEY_POSITION].add(entity_id)
        else:
            self._tilts[KEY_POSITION].discard(entity_id)

        if update_state:
            self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Register listeners."""
        for entity_id in self._entities:
            new_state = self.hass.states.get(entity_id)
            self.update_supported_features(entity_id, new_state, update_state=False)
        async_track_state_change_event(
            self.hass, self._entities, self._update_supported_features_event
        )
        await self.async_update()

    @property
    def name(self):
        """Return the name of the cover."""
        return self._name

    @property
    def assumed_state(self):
        """Enable buttons even if at end position."""
        return self._assumed_state

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
    def is_opening(self):
        """Return if the cover is opening or not."""
        return self._is_opening

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return self._is_closing

    @property
    def current_cover_position(self) -> Optional[int]:
        """Return current position for all covers."""
        return self._cover_position

    @property
    def current_cover_tilt_position(self):
        """Return current tilt position for all covers."""
        return self._tilt_position

    @property
    def device_state_attributes(self):
        """Return the state attributes for the cover group."""
        return {ATTR_ENTITY_ID: self._entities}

    async def async_open_cover(self, **kwargs):
        """Move the covers up."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER, data, blocking=True, context=self._context
        )

    async def async_close_cover(self, **kwargs):
        """Move the covers down."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER, data, blocking=True, context=self._context
        )

    async def async_stop_cover(self, **kwargs):
        """Fire the stop action."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_STOP]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER, data, blocking=True, context=self._context
        )

    async def async_set_cover_position(self, **kwargs):
        """Set covers position."""
        data = {
            ATTR_ENTITY_ID: self._covers[KEY_POSITION],
            ATTR_POSITION: kwargs[ATTR_POSITION],
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_POSITION,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_open_cover_tilt(self, **kwargs):
        """Tilt covers open."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_close_cover_tilt(self, **kwargs):
        """Tilt covers closed."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop cover tilt."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_STOP]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_set_cover_tilt_position(self, **kwargs):
        """Set tilt position."""
        data = {
            ATTR_ENTITY_ID: self._tilts[KEY_POSITION],
            ATTR_TILT_POSITION: kwargs[ATTR_TILT_POSITION],
        }
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_update(self):
        """Update state and attributes."""
        self._assumed_state = False

        self._is_closed = True
        self._is_closing = False
        self._is_opening = False
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if not state:
                continue
            if state.state == STATE_OPEN:
                self._is_closed = False
                break
            if state.state == STATE_CLOSING:
                self._is_closing = True
                break
            if state.state == STATE_OPENING:
                self._is_opening = True
                break

        self._cover_position = None
        if self._covers[KEY_POSITION]:
            position = -1
            self._cover_position = 0 if self.is_closed else 100
            for entity_id in self._covers[KEY_POSITION]:
                state = self.hass.states.get(entity_id)
                pos = state.attributes.get(ATTR_CURRENT_POSITION)
                if position == -1:
                    position = pos
                elif position != pos:
                    self._assumed_state = True
                    break
            else:
                if position != -1:
                    self._cover_position = position

        self._tilt_position = None
        if self._tilts[KEY_POSITION]:
            position = -1
            self._tilt_position = 100
            for entity_id in self._tilts[KEY_POSITION]:
                state = self.hass.states.get(entity_id)
                pos = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
                if position == -1:
                    position = pos
                elif position != pos:
                    self._assumed_state = True
                    break
            else:
                if position != -1:
                    self._tilt_position = position

        supported_features = 0
        supported_features |= (
            SUPPORT_OPEN | SUPPORT_CLOSE if self._covers[KEY_OPEN_CLOSE] else 0
        )
        supported_features |= SUPPORT_STOP if self._covers[KEY_STOP] else 0
        supported_features |= SUPPORT_SET_POSITION if self._covers[KEY_POSITION] else 0
        supported_features |= (
            SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT if self._tilts[KEY_OPEN_CLOSE] else 0
        )
        supported_features |= SUPPORT_STOP_TILT if self._tilts[KEY_STOP] else 0
        supported_features |= (
            SUPPORT_SET_TILT_POSITION if self._tilts[KEY_POSITION] else 0
        )
        self._supported_features = supported_features

        if not self._assumed_state:
            for entity_id in self._entities:
                state = self.hass.states.get(entity_id)
                if state and state.attributes.get(ATTR_ASSUMED_STATE):
                    self._assumed_state = True
                    break
