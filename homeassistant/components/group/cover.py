"""Platform allowing several cover to be grouped into one cover."""

import asyncio
from typing import Any, override

import probatio

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_SPEED,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    PLATFORM_SCHEMA as COVER_PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverEntityStateAttribute,
    CoverState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityStateAttribute,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity
from .util import reduce_attribute

KEY_OPEN_CLOSE = "open_close"
KEY_STOP = "stop"
KEY_POSITION = "position"

DEFAULT_NAME = "Cover Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = COVER_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_ENTITIES): cv.entities_domain(COVER_DOMAIN),
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        probatio.Optional(CONF_UNIQUE_ID): cv.string,
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
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    @override
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

        features = new_state.attributes.get(EntityStateAttribute.SUPPORTED_FEATURES, 0)

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

    def _member_speeds(self, entity_id: str) -> list[str]:
        """Return the speeds a member supports.

        Core validates a requested speed against this list, whether or not the
        member sets the speed feature.
        """
        if not (state := self.hass.states.get(entity_id)):
            return []
        return (
            state.attributes.get(CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS) or []
        )

    async def _async_call_members(
        self, service: str, entity_ids: set[str], data: dict[str, Any]
    ) -> None:
        """Call a cover service for the given members."""
        await self.hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_ids, **data},
            blocking=True,
            context=self._context,
        )

    async def _async_call_with_speed(
        self,
        service: str,
        feature: CoverEntityFeature,
        entity_ids: set[str],
        data: dict[str, Any],
        speed: str | None,
    ) -> None:
        """Call a service, passing the speed to the members that list it.

        Other members move at their default speed.
        """
        # One call lets core reject a member without the action before any
        # member moves
        if speed is None or any(
            (state := self.hass.states.get(entity_id))
            and state.state != STATE_UNAVAILABLE
            and not state.attributes.get(EntityStateAttribute.SUPPORTED_FEATURES, 0)
            & feature
            for entity_id in entity_ids
        ):
            await self._async_call_members(service, entity_ids, data)
            return

        with_speed = {
            entity_id
            for entity_id in entity_ids
            if speed in self._member_speeds(entity_id)
        }
        # Call all members before raising the first error, as core does
        results = await asyncio.gather(
            *(
                self._async_call_members(service, members, member_data)
                for members, member_data in (
                    (entity_ids - with_speed, data),
                    (with_speed, {**data, ATTR_SPEED: speed}),
                )
                if members
            ),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Move the covers up."""
        await self._async_call_with_speed(
            SERVICE_OPEN_COVER,
            CoverEntityFeature.OPEN,
            self._covers[KEY_OPEN_CLOSE],
            {},
            kwargs.get(ATTR_SPEED),
        )

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Move the covers down."""
        await self._async_call_with_speed(
            SERVICE_CLOSE_COVER,
            CoverEntityFeature.CLOSE,
            self._covers[KEY_OPEN_CLOSE],
            {},
            kwargs.get(ATTR_SPEED),
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Fire the stop action."""
        data = {ATTR_ENTITY_ID: self._covers[KEY_STOP]}
        await self.hass.services.async_call(
            COVER_DOMAIN, SERVICE_STOP_COVER, data, blocking=True, context=self._context
        )

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set covers position."""
        await self._async_call_with_speed(
            SERVICE_SET_COVER_POSITION,
            CoverEntityFeature.SET_POSITION,
            self._covers[KEY_POSITION],
            {ATTR_POSITION: kwargs[ATTR_POSITION]},
            kwargs.get(ATTR_SPEED),
        )

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt covers open."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER_TILT,
            data,
            blocking=True,
            context=self._context,
        )

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Tilt covers closed."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_OPEN_CLOSE]}
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER_TILT,
            data,
            blocking=True,
            context=self._context,
        )

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        data = {ATTR_ENTITY_ID: self._tilts[KEY_STOP]}
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER_TILT,
            data,
            blocking=True,
            context=self._context,
        )

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set tilt position."""
        data = {
            ATTR_ENTITY_ID: self._tilts[KEY_POSITION],
            ATTR_TILT_POSITION: kwargs[ATTR_TILT_POSITION],
        }
        await self.hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_TILT_POSITION,
            data,
            blocking=True,
            context=self._context,
        )

    @callback
    @override
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
        self._update_assumed_state_from_members()
        for entity_id in self._entity_ids:
            if not (state := self.hass.states.get(entity_id)):
                continue
            if state.state == CoverState.OPEN:
                self._attr_is_closed = False
                continue
            if state.state == CoverState.CLOSED:
                continue
            if state.state == CoverState.CLOSING:
                self._attr_is_closing = True
                continue
            if state.state == CoverState.OPENING:
                self._attr_is_opening = True
                continue
        if not valid_state:
            # Set as unknown if all members are unknown or unavailable
            self._attr_is_closed = None

        position_covers = self._covers[KEY_POSITION]
        all_position_states = [self.hass.states.get(x) for x in position_covers]
        position_states: list[State] = list(filter(None, all_position_states))
        self._attr_current_cover_position = reduce_attribute(
            position_states, CoverEntityStateAttribute.CURRENT_POSITION
        )

        # Member order keeps the speed order of each integration
        speeds = dict.fromkeys(
            speed
            for entity_id in self._entity_ids
            for speed in self._member_speeds(entity_id)
        )
        self._attr_supported_speeds = list(speeds) or None

        tilt_covers = self._tilts[KEY_POSITION]
        all_tilt_states = [self.hass.states.get(x) for x in tilt_covers]
        tilt_states: list[State] = list(filter(None, all_tilt_states))
        self._attr_current_cover_tilt_position = reduce_attribute(
            tilt_states, CoverEntityStateAttribute.CURRENT_TILT_POSITION
        )

        supported_features = CoverEntityFeature(0)
        if self._covers[KEY_OPEN_CLOSE]:
            supported_features |= CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
        supported_features |= CoverEntityFeature.STOP if self._covers[KEY_STOP] else 0
        if self._covers[KEY_POSITION]:
            supported_features |= CoverEntityFeature.SET_POSITION
        if self._attr_supported_speeds:
            supported_features |= CoverEntityFeature.SPEED
        if self._tilts[KEY_OPEN_CLOSE]:
            supported_features |= (
                CoverEntityFeature.OPEN_TILT | CoverEntityFeature.CLOSE_TILT
            )
        if self._tilts[KEY_STOP]:
            supported_features |= CoverEntityFeature.STOP_TILT
        if self._tilts[KEY_POSITION]:
            supported_features |= CoverEntityFeature.SET_TILT_POSITION
        self._attr_supported_features = supported_features
