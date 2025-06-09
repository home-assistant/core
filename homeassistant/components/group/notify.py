"""Group platform for notify component."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    DOMAIN as NOTIFY_DOMAIN,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    SERVICE_SEND_MESSAGE,
    BaseNotificationService,
    NotifyEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ACTION,
    CONF_ENTITIES,
    CONF_SERVICE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .entity import GroupEntity

CONF_SERVICES = "services"


def _backward_compat_schema(value: Any | None) -> Any:
    """Backward compatibility for notify service schemas."""

    if not isinstance(value, dict):
        return value

    # `service` has been renamed to `action`
    if CONF_SERVICE in value:
        if CONF_ACTION in value:
            raise vol.Invalid(
                "Cannot specify both 'service' and 'action'. Please use 'action' only."
            )
        value[CONF_ACTION] = value.pop(CONF_SERVICE)

    return value


PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERVICES): vol.All(
            cv.ensure_list,
            [
                vol.All(
                    _backward_compat_schema,
                    {
                        vol.Required(CONF_ACTION): cv.slug,
                        vol.Optional(ATTR_DATA): dict,
                    },
                )
            ],
        )
    }
)


def add_defaults(
    input_data: dict[str, Any], default_data: Mapping[str, Any]
) -> dict[str, Any]:
    """Deep update a dictionary with default values."""
    for key, val in default_data.items():
        if isinstance(val, Mapping):
            input_data[key] = add_defaults(input_data.get(key, {}), val)
        elif key not in input_data:
            input_data[key] = val
    return input_data


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> GroupNotifyPlatform:
    """Get the Group notification service."""
    return GroupNotifyPlatform(hass, config[CONF_SERVICES])


class GroupNotifyPlatform(BaseNotificationService):
    """Implement the notification service for the group notify platform."""

    def __init__(self, hass: HomeAssistant, entities: list[dict[str, Any]]) -> None:
        """Initialize the service."""
        self.hass = hass
        self.entities = entities

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send message to all entities in the group."""
        payload: dict[str, Any] = {ATTR_MESSAGE: message}
        payload.update({key: val for key, val in kwargs.items() if val})

        tasks: list[asyncio.Task[Any]] = []
        for entity in self.entities:
            sending_payload = deepcopy(payload.copy())
            if (default_data := entity.get(ATTR_DATA)) is not None:
                add_defaults(sending_payload, default_data)
            tasks.append(
                asyncio.create_task(
                    self.hass.services.async_call(
                        NOTIFY_DOMAIN,
                        entity[CONF_ACTION],
                        sending_payload,
                        blocking=True,
                    )
                )
            )

        if tasks:
            await asyncio.wait(tasks)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Notify Group config entry."""
    registry = er.async_get(hass)
    entities = er.async_validate_entity_ids(
        registry, config_entry.options[CONF_ENTITIES]
    )

    async_add_entities(
        [NotifyGroup(config_entry.entry_id, config_entry.title, entities)]
    )


@callback
def async_create_preview_notify(
    hass: HomeAssistant, name: str, validated_config: dict[str, Any]
) -> NotifyGroup:
    """Create a preview notify group."""
    return NotifyGroup(
        None,
        name,
        validated_config[CONF_ENTITIES],
    )


class NotifyGroup(GroupEntity, NotifyEntity):
    """Representation of a NotifyGroup."""

    _attr_available: bool = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        entity_ids: list[str],
    ) -> None:
        """Initialize a NotifyGroup."""
        self._entity_ids = entity_ids
        self._attr_name = name
        self._attr_extra_state_attributes = {ATTR_ENTITY_ID: entity_ids}
        self._attr_unique_id = unique_id

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message to all members of the group."""
        await self.hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_SEND_MESSAGE,
            {
                ATTR_MESSAGE: message,
                ATTR_TITLE: title,
                ATTR_ENTITY_ID: self._entity_ids,
            },
            blocking=True,
            context=self._context,
        )

    @callback
    def async_update_group_state(self) -> None:
        """Query all members and determine the notify group state."""
        # Set group as unavailable if all members are unavailable or missing
        self._attr_available = any(
            state.state != STATE_UNAVAILABLE
            for entity_id in self._entity_ids
            if (state := self.hass.states.get(entity_id)) is not None
        )
