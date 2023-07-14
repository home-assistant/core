"""Siren support for switch entities."""
from __future__ import annotations

from homeassistant.components.siren import (
    DOMAIN as SIREN_DOMAIN,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import BaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Siren Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            SirenSwitch(
                hass,
                config_entry.title,
                SIREN_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class SirenSwitch(BaseToggleEntity, SirenEntity):
    """Represents a Switch as a Siren."""

    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
