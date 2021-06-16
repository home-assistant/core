"""This platform allows several cover to be grouped into one cover."""
from __future__ import annotations

from typing import Any

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
from homeassistant.core import CoreState, Event, HomeAssistant, State
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from . import GroupEntity

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Group Cover platform."""
    async_add_entities([CoverGroup(config[CONF_NAME], config[CONF_ENTITIES])])


class CoverGroup(GroupEntity, CoverEntity):
    """Representation of a CoverGroup."""

    _attr_is_closed: bool | None = False
    _attr_is_opening: bool | None = False
    _attr_is_closing: bool | None = False
    _attr_current_cover_position: int | None = 100
    _attr_assumed_state: bool = True

    def __init__(self, name: str, entities: list[str]) -> None:
        """Initialize a CoverGroup entity."""
        self._entities = entities
        self._covers: dict[str, set[str]] = {
            KEY_OPEN_CLOSE: set(),
            KEY_STOP: set(),
            KEY_POSITION: set(),
        }
        self._tilts: dict[str, set[str]] = {
            KEY_OPEN_CLOSE: set(),
            KEY_STOP: set(),
            KEY_POSITION: set(),
        }

        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entities}

    async def _update_supported_features_event(self, event: Event) -> None:
        self.async_set_context(event.context)
        entity = event.data.get("entity_id")
        if entity is not None:
            await self.async_update_supported_features(
                entity, event.data.get("new_state")
            )

    async def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
        update_state: bool = True,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._covers.values():
                values.discard(entity_id)
            for values in self._tilts.values():
                values.discard(entity_id)
            if update_state:
                await self.async_defer_or_update_ha_state()
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
            await self.async_defer_or_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register listeners."""
        for entity_id in self._entities:
            new_state = self.hass.states.get(entity_id)
            if new_state is None:
                continue
            await self.async_update_supported_features(
                entity_id, new_state, update_state=False
            )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._entities, self._update_supported_features_event
            )
        )

        if self.hass.state == CoreState.running:
            await self.async_update()
            return
        await super().async_added_to_hass()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the covers up."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER, data, blocking=True, context=self._context
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the covers down."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER, data, blocking=True, context=self._context
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_STOP]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER, data, blocking=True, context=self._context
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
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

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt covers open."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_OPEN_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt covers closed."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_CLOSE_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_STOP]}
        await self.hass.services.async_call(
            DOMAIN, SERVICE_STOP_COVER_TILT, data, blocking=True, context=self._context
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
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

    async def async_update(self) -> None:
        """Update state and attributes."""
        self._attr_assumed_state = False

        self._attr_is_closed = True
        self._attr_is_closing = False
        self._attr_is_opening = False
        for entity_id in self._entities:
            state = self.hass.states.get(entity_id)
            if not state:
                continue
            if state.state == STATE_OPEN:
                self._attr_is_closed = False
                break
            if state.state == STATE_CLOSING:
                self._attr_is_closing = True
                break
            if state.state == STATE_OPENING:
                self._attr_is_opening = True
                break

        self._attr_current_cover_position = None
        if self._covers[KEY_POSITION]:
            position: int | None = -1
            self._attr_current_cover_position = 0 if self.is_closed else 100
            for entity_id in self._covers[KEY_POSITION]:
                state = self.hass.states.get(entity_id)
                if state is None:
                    continue
                pos = state.attributes.get(ATTR_CURRENT_POSITION)
                if position == -1:
                    position = pos
                elif position != pos:
                    self._attr_assumed_state = True
                    break
            else:
                if position != -1:
                    self._attr_current_cover_position = position

        self._attr_current_cover_tilt_position = None
        if self._tilts[KEY_POSITION]:
            position = -1
            self._attr_current_cover_tilt_position = 100
            for entity_id in self._tilts[KEY_POSITION]:
                state = self.hass.states.get(entity_id)
                if state is None:
                    continue
                pos = state.attributes.get(ATTR_CURRENT_TILT_POSITION)
                if position == -1:
                    position = pos
                elif position != pos:
                    self._attr_assumed_state = True
                    break
            else:
                if position != -1:
                    self._attr_current_cover_tilt_position = position

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
        self._attr_supported_features = supported_features

        if not self._attr_assumed_state:
            for entity_id in self._entities:
                state = self.hass.states.get(entity_id)
                if state is None:
                    continue
                if state and state.attributes.get(ATTR_ASSUMED_STATE):
                    self._attr_assumed_state = True
                    break
