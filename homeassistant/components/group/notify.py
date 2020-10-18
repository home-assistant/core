"""Group platform for notify component."""
import asyncio
from collections.abc import Mapping
from copy import deepcopy

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    DOMAIN,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import ATTR_SERVICE
import homeassistant.helpers.config_validation as cv

# mypy: allow-untyped-calls, allow-untyped-defs, no-check-untyped-defs

CONF_SERVICES = "services"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_SERVICES): vol.All(
            cv.ensure_list,
            [{vol.Required(ATTR_SERVICE): cv.slug, vol.Optional(ATTR_DATA): dict}],
        )
    }
)


def update(input_dict, update_source):
    """Deep update a dictionary.

    Async friendly.
    """
    for key, val in update_source.items():
        if isinstance(val, Mapping):
            recurse = update(input_dict.get(key, {}), val)
            input_dict[key] = recurse
        else:
            input_dict[key] = update_source[key]
    return input_dict


async def async_get_service(hass, config, discovery_info=None):
    """Get the Group notification service."""
    return GroupNotifyPlatform(hass, config.get(CONF_SERVICES))


class GroupNotifyPlatform(BaseNotificationService):
    """Implement the notification service for the group notify platform."""

    def __init__(self, hass, entities):
        """Initialize the service."""
        self.hass = hass
        self.entities = entities

    async def async_send_message(self, message="", **kwargs):
        """Send message to all entities in the group."""
        payload = {ATTR_MESSAGE: message}
        payload.update({key: val for key, val in kwargs.items() if val})

        tasks = []
        for entity in self.entities:
            sending_payload = deepcopy(payload.copy())
            if entity.get(ATTR_DATA) is not None:
                update(sending_payload, entity.get(ATTR_DATA))
            tasks.append(
                self.hass.services.async_call(
                    DOMAIN, entity.get(ATTR_SERVICE), sending_payload
                )
            )

        if tasks:
            await asyncio.wait(tasks)
