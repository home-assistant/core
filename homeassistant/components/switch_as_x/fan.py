"""Fan support for switch entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import BaseToggleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize Fan Switch config entry."""
    registry = er.async_get(hass)
    entity_id = er.async_validate_entity_id(
        registry, config_entry.options[CONF_ENTITY_ID]
    )

    async_add_entities(
        [
            FanSwitch(
                hass,
                config_entry.title,
                FAN_DOMAIN,
                entity_id,
                config_entry.entry_id,
            )
        ]
    )


class FanSwitch(BaseToggleEntity, FanEntity):
    """Represents a Switch as a Fan."""

    _attr_supported_features = FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON

    @property
    def is_on(self) -> bool | None:
        """Return true if the entity is on.

        Fan logic uses speed percentage or preset mode to determine
        if it's on or off, however, when using a wrapped switch, we
        just use the wrapped switch's state.
        """
        return self._attr_is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan.

        Arguments of the turn_on methods fan entity differ,
        thus we need to override them here.
        """
        await super().async_turn_on()
