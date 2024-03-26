"""RASC integration helpers."""
from __future__ import annotations

from logging import Logger
from typing import Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_SERVICE, RASC_RESPONSE
from homeassistant.core import HomeAssistant


def fire(
    hass: HomeAssistant,
    rasc_type: str,
    entity_id: str,
    action: str,
    logger: Logger | None = None,
    service_data: dict[str, Any] | None = None,
):
    """Fire rasc response."""
    if logger:
        logger.info("%s %s: %s", entity_id, action, rasc_type)
    service_data = service_data or {}
    hass.bus.async_fire(
        RASC_RESPONSE,
        {
            "type": rasc_type,
            ATTR_SERVICE: action,
            ATTR_ENTITY_ID: entity_id,
            **{str(key): value for key, value in service_data.items()},
        },
    )
