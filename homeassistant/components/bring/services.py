"""Actions for Bring! integration."""

from __future__ import annotations

from bring_api import BringNotificationType
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.service import entity_service_call

from .const import (
    ATTR_ITEM_NAME,
    ATTR_NOTIFICATION_TYPE,
    DOMAIN,
    SERVICE_PUSH_NOTIFICATION,
)


def async_get_entities(hass: HomeAssistant) -> dict[str, Entity]:
    """Get entities for a domain."""
    entities: dict[str, Entity] = {}
    for platform in async_get_platforms(hass, DOMAIN):
        entities.update(platform.entities)
    return entities


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up actions for bring integration."""

    async def _async_send_message(call: ServiceCall) -> None:
        await entity_service_call(
            hass, async_get_entities(hass), "async_send_message", call
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=SERVICE_PUSH_NOTIFICATION,
        schema=cv.make_entity_service_schema(
            {
                vol.Required(ATTR_NOTIFICATION_TYPE): vol.All(
                    vol.Upper, vol.Coerce(BringNotificationType)
                ),
                vol.Optional(ATTR_ITEM_NAME): cv.string,
            },
        ),
        service_func=_async_send_message,
    )
