"""Support for ESPHome fans."""
from __future__ import annotations

import math
from typing import Any

from aioesphomeapi import EntityInfo, FanDirection, FanInfo, FanSpeed, FanState

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry
from .enum_mapper import EsphomeEnumMapper

ORDERED_NAMED_FAN_SPEEDS = [FanSpeed.LOW, FanSpeed.MEDIUM, FanSpeed.HIGH]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome fans based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=FanInfo,
        entity_type=EsphomeFan,
        state_type=FanState,
    )


_FAN_DIRECTIONS: EsphomeEnumMapper[FanDirection, str] = EsphomeEnumMapper(
    {
        FanDirection.FORWARD: DIRECTION_FORWARD,
        FanDirection.REVERSE: DIRECTION_REVERSE,
    }
)


class EsphomeFan(EsphomeEntity[FanInfo, FanState], FanEntity):
    """A fan implementation for ESPHome."""

    _supports_speed_levels: bool = True

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self._async_set_percentage(percentage)

    async def _async_set_percentage(self, percentage: int | None) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return

        data: dict[str, Any] = {"key": self._key, "state": True}
        if percentage is not None:
            if self._supports_speed_levels:
                data["speed_level"] = math.ceil(
                    percentage_to_ranged_value(
                        (1, self._static_info.supported_speed_levels), percentage
                    )
                )
            else:
                named_speed = percentage_to_ordered_list_item(
                    ORDERED_NAMED_FAN_SPEEDS, percentage
                )
                data["speed"] = named_speed
        await self._client.fan_command(**data)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        await self._async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self._client.fan_command(key=self._key, state=False)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._client.fan_command(key=self._key, oscillating=oscillating)

    async def async_set_direction(self, direction: str) -> None:
        """Set direction of the fan."""
        await self._client.fan_command(
            key=self._key, direction=_FAN_DIRECTIONS.from_hass(direction)
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._client.fan_command(key=self._key, preset_mode=preset_mode)

    @property
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._state.state

    @property
    @esphome_state_property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self._supports_speed_levels:
            return ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS,
                self._state.speed,  # type: ignore[misc]
            )

        return ranged_value_to_percentage(
            (1, self._static_info.supported_speed_levels), self._state.speed_level
        )

    @property
    @esphome_state_property
    def oscillating(self) -> bool | None:
        """Return the oscillation state."""
        return self._state.oscillating

    @property
    @esphome_state_property
    def current_direction(self) -> str | None:
        """Return the current fan direction."""
        return _FAN_DIRECTIONS.from_esphome(self._state.direction)

    @property
    @esphome_state_property
    def preset_mode(self) -> str | None:
        """Return the current fan preset mode."""
        return self._state.preset_mode

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        api_version = self._api_version
        supports_speed_levels = api_version.major == 1 and api_version.minor > 3
        self._supports_speed_levels = supports_speed_levels
        flags = FanEntityFeature(0)
        if static_info.supports_oscillation:
            flags |= FanEntityFeature.OSCILLATE
        if static_info.supports_speed:
            flags |= FanEntityFeature.SET_SPEED
        if static_info.supports_direction:
            flags |= FanEntityFeature.DIRECTION
        if static_info.supported_preset_modes:
            flags |= FanEntityFeature.PRESET_MODE
        self._attr_supported_features = flags
        self._attr_preset_modes = static_info.supported_preset_modes
        if not supports_speed_levels:
            self._attr_speed_count = len(ORDERED_NAMED_FAN_SPEEDS)
        else:
            self._attr_speed_count = static_info.supported_speed_levels
