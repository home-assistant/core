"""Support for Bang & Olufsen diagnostics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import BangOlufsenConfigEntry
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BangOlufsenConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    if TYPE_CHECKING:
        assert config_entry.unique_id

    # Get media_player entity
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id(
        MEDIA_PLAYER_DOMAIN, DOMAIN, config_entry.unique_id
    )

    if TYPE_CHECKING:
        assert entity_id

    entity = entity_registry.async_get(entity_id)

    if TYPE_CHECKING:
        assert entity

    return {
        "config_entry": config_entry.as_dict(),
        "media_player": {
            CONF_NAME: entity.name,
            CONF_ENTITY_ID: entity.entity_id,
            CONF_UNIQUE_ID: entity.unique_id,
            "capabilities": entity.capabilities,
        },
        "websocket_connected": config_entry.runtime_data.client.websocket_connected,
    }
