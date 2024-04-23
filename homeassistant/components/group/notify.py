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
    DOMAIN,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import ATTR_SERVICE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_SERVICES = "services"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERVICES): vol.All(
            cv.ensure_list,
            [{vol.Required(ATTR_SERVICE): cv.slug, vol.Optional(ATTR_DATA): dict}],
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
                        DOMAIN, entity[ATTR_SERVICE], sending_payload, blocking=True
                    )
                )
            )

        if tasks:
            await asyncio.wait(tasks)
