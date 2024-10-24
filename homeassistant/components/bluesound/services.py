"""Support for Bluesound devices."""

from __future__ import annotations

from typing import NamedTuple

import voluptuous as vol

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import ATTR_MASTER, DOMAIN

SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_JOIN = "join"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_UNJOIN = "unjoin"

BS_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

BS_JOIN_SCHEMA = BS_SCHEMA.extend({vol.Required(ATTR_MASTER): cv.entity_id})


class ServiceMethodDetails(NamedTuple):
    """Details for SERVICE_TO_METHOD mapping."""

    method: str
    schema: vol.Schema


SERVICE_TO_METHOD = {
    SERVICE_JOIN: ServiceMethodDetails(method="async_join", schema=BS_JOIN_SCHEMA),
    SERVICE_UNJOIN: ServiceMethodDetails(method="async_unjoin", schema=BS_SCHEMA),
    SERVICE_SET_TIMER: ServiceMethodDetails(
        method="async_increase_timer", schema=BS_SCHEMA
    ),
    SERVICE_CLEAR_TIMER: ServiceMethodDetails(
        method="async_clear_timer", schema=BS_SCHEMA
    ),
}


def setup_services(hass: HomeAssistant) -> None:
    """Set up services for Bluesound component."""

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to method of Bluesound devices."""
        if not (method := SERVICE_TO_METHOD.get(service.service)):
            return

        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            target_players = [
                player for player in hass.data[DOMAIN] if player.entity_id in entity_ids
            ]
        else:
            target_players = hass.data[DOMAIN]

        for player in target_players:
            await getattr(player, method.method)(**params)

    for service, method in SERVICE_TO_METHOD.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, schema=method.schema
        )
