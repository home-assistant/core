"""Platform allowing several button entities to be grouped into one single button."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.button import (
    DOMAIN,
    PLATFORM_SCHEMA as BUTTON_PLATFORM_SCHEMA,
    SERVICE_PRESS,
    ButtonEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ENTITIES,
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

DEFAULT_NAME = "Button group"

# No limit on parallel updates to enable a group calling another group
PARALLEL_UPDATES = 0

PLATFORM_SCHEMA = BUTTON_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITIES): cv.entities_domain(DOMAIN),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    _: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    __: DiscoveryInfoType | None = None,
) -> None:
    """Set up the button group platform."""
    async_add_entities(
        [
            ButtonGroup(
                config.get(CONF_UNIQUE_ID),
                config[CONF_NAME],
                config[CONF_ENTITIES],
            )
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize button group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )
    async_add_entities(
        [
            ButtonGroup(
                config_entry.entry_id,
                config_entry.title,
                entities,
            )
        ]
    )


@callback
def async_create_preview_button(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> ButtonGroup:
    """Create a preview button."""
    return ButtonGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class ButtonGroup(GroupEntity, ButtonEntity):
    """Representation of an button group."""

    _attr_available = False
    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
    ) -> None:
        """Initialize a button group."""
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id

    async def async_press(self) -> None:
        """Forward the press to all buttons in the group."""
        await self.hass.services.async_call(
            DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: self._entity_ids},
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the button group state."""
        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(
            state.state != STATE_UNAVAILABLE
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        )
