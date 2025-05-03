"""Platform allowing several sirens to be grouped into one siren."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    PLATFORM_SCHEMA as SIREN_PLATFORM_SCHEMA,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

DEFAULT_NAME = "Siren Group"
CONF_ALL = "all"

SUPPORT_GROUP_SIREN = (
    SirenEntityFeature.TURN_ON
    | SirenEntityFeature.TURN_OFF
    | SirenEntityFeature.TONES
    | SirenEntityFeature.DURATION
    | SirenEntityFeature.VOLUME_SET
)

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = SIREN_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(SIREN_DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ALL, default=False): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Siren Group platform."""
    async_add_entities(
        [
            SirenGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
                config.get(CONF_ALL, False),
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Siren Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            SirenGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
                config_entry.options.get(CONF_ALL),
            )
        ]
    )


@callback
def async_create_preview_siren(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> SirenGroup:
    """Create a preview sensor."""
    return SirenGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
        validated_config.get(CONF_ALL, False),
    )


class SirenGroup(GroupEntity, SirenEntity):
    """Representation of a siren group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
        mode: bool | None,
    ) -> None:
        """Initialize a siren group."""
        self._entity_ids = entity_ids

        self._attr_name = name
        self._attr_extra_state_attributes = {
            ATTR_ENTITY_ID: entity_ids,
            "available_tones": [],
        }
        self._attr_unique_id = unique_id
        self.mode = any
        if mode:
            self.mode = all

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Forward the turn_on command with kwargs to all sirens in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids, **kwargs}

        await self.hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_ON,
            data,
            blocking=True,
            context=self._context,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Forward the turn_off command to all sirens in the group."""
        data = {ATTR_ENTITY_ID: self._entity_ids}
        await self.hass.services.async_call(
            SIREN_DOMAIN,
            SERVICE_TURN_OFF,
            data,
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the siren group state."""
        states = [
            state
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        ]

        valid_state = self.mode(
            state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE) for state in states
        )

        if not valid_state:
            self._attr_is_on = None
        else:
            self._attr_is_on = self.mode(state.state == STATE_ON for state in states)

        self._attr_available = any(state.state != STATE_UNAVAILABLE for state in states)

        self._attr_supported_features = SirenEntityFeature(0)
        available_tones = set()  # Collect available tones from all entities
        for state in states:
            if (features := state.attributes.get(ATTR_SUPPORTED_FEATURES)) is not None:
                self._attr_supported_features |= features
            if tones := state.attributes.get("available_tones"):
                available_tones.update(tones)

        self._attr_supported_features &= SUPPORT_GROUP_SIREN
        self._attr_extra_state_attributes["available_tones"] = list(available_tones)
