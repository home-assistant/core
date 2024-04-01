"""Fans on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation fan from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms.pop(Platform.FAN, [])
    entities = [ZhaFan(entity_data) for entity_data in entities_to_create]
    async_add_entities(entities)

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZhaFan(FanEntity, ZHAEntity):
    """Representation of a ZHA fan."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_translation_key: str = "fan"

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self.entity_data.entity.preset_mode

    @property
    def preset_modes(self) -> list[str]:
        """Return the available preset modes."""
        return self.entity_data.entity.preset_modes

    @property
    def default_on_percentage(self) -> int:
        """Return the default on percentage."""
        return self.entity_data.entity.default_on_percentage

    @property
    def speed_range(self) -> tuple[int, int]:
        """Return the range of speeds the fan supports. Off is not included."""
        return self.entity_data.entity.speed_range

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self.entity_data.entity.speed_count

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(
            percentage=percentage, preset_mode=preset_mode, **kwargs
        )
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off(**kwargs)
        await self.async_update_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self.entity_data.entity.async_set_percentage(percentage)
        await self.async_update_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the fan."""
        await self.entity_data.entity.async_set_preset_mode(preset_mode)
        await self.async_update_ha_state()

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self.entity_data.entity.percentage
