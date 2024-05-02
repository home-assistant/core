"""Platform allowing several cover to be grouped into one cover."""

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
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity
from .util import reduce_attribute

KEY_OPEN_CLOSE = "open_close"
KEY_STOP = "stop"
KEY_POSITION = "position"

DEFAULT_NAME = "Cover Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Cover Group platform."""
    async_add_entities(
        [
            CoverGroup(
                config.get(CONF_UNIQUE_ID), config[CONF_NAME], config[CONF_ENTITIES]
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Cover Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities(
        [CoverGroup(config_entry.entry_id, config_entry.title, entities)]
    )


@callback
def async_create_preview_cover(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> CoverGroup:
    """Create a preview sensor."""
    return CoverGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class CoverGroup(GroupEntity, CoverEntity):
    """Representation of a CoverGroup."""

    _attr_available: bool = False
    _attr_is_closed: bool | None = None
    _attr_is_opening: bool | None = False
    _attr_is_closing: bool | None = False
    _attr_current_cover_position: int | None = 100

    def __init__(self, unique_id: str | None, name: str, entities: list[str]) -> None:
        """Initialize a CoverGroup entity."""
        self._entity_ids = entities
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
        self._attr_unique_id = unique_id

    @callback
    def async_update_supported_features(
        self,
        entity_id: str,
        new_state: State | None,
    ) -> None:
        """Update dictionaries with supported features."""
        if not new_state:
            for values in self._covers.values():
                values.discard(entity_id)
            for values in self._tilts.values():
                values.discard(entity_id)
            return

        features = new_state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)

        if features & (CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE):
            self._covers[KEY_OPEN_CLOSE].add(entity_id)
        else:
            self._covers[KEY_OPEN_CLOSE].discard(entity_id)
        if features & (CoverEntityFeature.STOP):
            self._covers[KEY_STOP].add(entity_id)
        else:
            self._covers[KEY_STOP].discard(entity_id)
        if features & (CoverEntityFeature.SET_POSITION):
            self._covers[KEY_POSITION].add(entity_id)
        else:
            self._covers[KEY_POSITION].discard(entity_id)

        if features & (CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT):
            self._tilts[KEY_OPEN_CLOSE].add(entity_id)
        else:
            self._tilts[KEY_OPEN_CLOSE].discard(entity_id)
        if features & (CoverEntityFeature.STOP_TILT):
            self._tilts[KEY_STOP].add(entity_id)
        else:
            self._tilts[KEY_STOP].discard(entity_id)
        if features & (CoverEntityFeature.SET_TILT_POSITION):
            self._tilts[KEY_POSITION].add(entity_id)
        else:
            self._tilts[KEY_POSITION].discard(entity_id)

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

    @callback
    def async_update_group_state(self) -> None:
        """Update state and attributes."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        valid_state = any(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)

        self._attr_is_closed = True
        self._attr_is_closing = False
        self._attr_is_opening = False
        for entity_id in self._entity_ids:
            if not (state := self.hass.states.get(entity_id)):
                continue
            if state.state == STATE_OPEN:
                self._attr_is_closed = False
                continue
            if state.state == STATE_CLOSED:
                continue
            if state.state == STATE_CLOSING:
                self._attr_is_closing = True
                continue
            if state.state == STATE_OPENING:
                self._attr_is_opening = True
                continue
        if not valid_state:
            # Set as unknown if all members are unknown or unavailable
            self._attr_is_closed = None

        position_covers = self._covers[KEY_POSITION]
        all_position_states = [self.hass.states.get(x) for x in position_covers]
        position_states: list[State] = list(filter(None, all_position_states))
        self._attr_current_cover_position = reduce_attribute(
            position_states, ATTR_CURRENT_POSITION
        )

        tilt_covers = self._tilts[KEY_POSITION]
        all_tilt_states = [self.hass.states.get(x) for x in tilt_covers]
        tilt_states: list[State] = list(filter(None, all_tilt_states))
        self._attr_current_cover_tilt_position = reduce_attribute(
            tilt_states, ATTR_CURRENT_TILT_POSITION
        )

        supported_features = CoverEntityFeature(0)
        if self._covers[KEY_OPEN_CLOSE]:
            supported_features |= CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        supported_features |= CoverEntityFeature.STOP if self._covers[KEY_STOP] else 0
        if self._covers[KEY_POSITION]:
            supported_features |= CoverEntityFeature.SET_POSITION
        if self._tilts[KEY_OPEN_CLOSE]:
            supported_features |= (
                CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT
            )
        if self._tilts[KEY_STOP]:
            supported_features |= CoverEntityFeature.STOP_TILT
        if self._tilts[KEY_POSITION]:
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        self._attr_supported_features = supported_features
