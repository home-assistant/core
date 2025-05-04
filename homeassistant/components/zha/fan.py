"""Fans on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
from typing import Any

from zha.application.platforms.fan.const import FanEntityFeature as ZHAFanEntityFeature

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    convert_zha_error_to_ha_error,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation fan from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.FAN]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, ZhaFan, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


class ZhaFan(FanEntity, ZHAEntity):
    """Representation of a ZHA fan."""

    _attr_translation_key: str = "fan"

    def __init__(self, entity_data: EntityData) -> None:
        """Initialize the ZHA fan."""
        super().__init__(entity_data)
        features = FanEntityFeature(0)
        zha_features: ZHAFanEntityFeature = self.entity_data.entity.supported_features

        if ZHAFanEntityFeature.DIRECTION in zha_features:
            features |= FanEntityFeature.DIRECTION
        if ZHAFanEntityFeature.OSCILLATE in zha_features:
            features |= FanEntityFeature.OSCILLATE
        if ZHAFanEntityFeature.PRESET_MODE in zha_features:
            features |= FanEntityFeature.PRESET_MODE
        if ZHAFanEntityFeature.SET_SPEED in zha_features:
            features |= FanEntityFeature.SET_SPEED
        if ZHAFanEntityFeature.TURN_ON in zha_features:
            features |= FanEntityFeature.TURN_ON
        if ZHAFanEntityFeature.TURN_OFF in zha_features:
            features |= FanEntityFeature.TURN_OFF

        self._attr_supported_features = features

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

    @convert_zha_error_to_ha_error
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the entity on."""
        await self.entity_data.entity.async_turn_on(
            percentage=percentage, preset_mode=preset_mode
        )
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.entity_data.entity.async_turn_off()
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self.entity_data.entity.async_set_percentage(percentage=percentage)
        self.async_write_ha_state()

    @convert_zha_error_to_ha_error
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode for the fan."""
        await self.entity_data.entity.async_set_preset_mode(preset_mode=preset_mode)
        self.async_write_ha_state()

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        return self.entity_data.entity.percentage
