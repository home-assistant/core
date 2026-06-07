"""Platform allowing several locks to be grouped into one lock."""

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    PLATFORM_SCHEMA as LOCK_PLATFORM_SCHEMA,
    LockEntity,
    LockEntityFeature,
    LockState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.group import GenericGroup
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

DEFAULT_NAME = "Lock Group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = LOCK_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(LOCK_DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Lock Group platform."""
    entities = {"entity_id": config[CONF_ENTITIES]}
    async_add_entities(
        [
            LockGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                entities,
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Lock Group config entry."""
    target_config = dict(config_entry.options[CONF_ENTITIES])
    entity_ids = target_config.get("entity_id", [])
    if entity_ids:
        registry = er.async_get(hass)
        entities = er.async_validate_entity_ids(registry, entity_ids)
        target_config["entity_id"] = entities
    async_add_entities(
        [
            LockGroup(
                config_entry.entry_id,
                config_entry.title,
                target_config,
            )
        ]
    )


@callback
def async_create_preview_lock(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> LockGroup:
    """Create a preview sensor."""
    return LockGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class LockGroup(GroupEntity, LockEntity):
    """Representation of a lock group."""

    _attr_available = False
    _attr_should_poll = False
    group: GenericGroup

    def __init__(
        self, unique_id: str | None, name: str, target_config: dict[str, Any]
    ) -> None:
        """Initialize a lock group."""
        super().__init__()
        self._target_config = target_config
        self._domain = LOCK_DOMAIN
        self.group = GenericGroup(self, target_config.get("entity_id", []))
        self._attr_supported_features = LockEntityFeature.OPEN
        self._attr_name = name
        self._attr_unique_id = unique_id

    def update_group_member(self, entities: set[str]) -> None:
        """Update the group member."""
        self.group._member_entity_ids = list(entities)  # noqa: SLF001

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the lock group state."""
        states = [
            state.state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        valid_state = any(
            state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            # Set as unknown if any member is unknown or unavailable
            self._attr_is_jammed = None
            self._attr_is_locking = None
            self._attr_is_opening = None
            self._attr_is_open = None
            self._attr_is_unlocking = None
            self._attr_is_locked = None
        else:
            # Set attributes based on member states and let the
            # lock entity sort out the correct state
            self._attr_is_jammed = LockState.JAMMED in states
            self._attr_is_locking = LockState.LOCKING in states
            self._attr_is_opening = LockState.OPENING in states
            self._attr_is_open = LockState.OPEN in states
            self._attr_is_unlocking = LockState.UNLOCKING in states
            self._attr_is_locked = all(state == LockState.LOCKED for state in states)

        self._attr_available = any(state != STATE_UNAVAILABLE for state in states)
