"""Inverse support for switch entities."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchEntity
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
    """Initialize Inverse Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            InvertSwitch(
                hass,
                config_entry.title,
                SWITCH_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class InvertSwitch(BaseToggleEntity, SwitchEntity):
    """Represents a Switch as Inversed."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is off."""
        return not self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn off original switch."""
        await super().async_turn_off()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn on original switch."""
        await super().async_turn_on()
