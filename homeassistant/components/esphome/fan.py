"""Support for ESPHome fans."""
from __future__ import annotations

import math
from typing import Any

from aioesphomeapi import FanDirection, FanInfo, FanSpeed, FanState

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import (
    EsphomeEntity,
    EsphomeEnumMapper,
    esphome_state_property,
    platform_async_setup_entry,
)

ORDERED_NAMED_FAN_SPEEDS = [FanSpeed.LOW, FanSpeed.MEDIUM, FanSpeed.HIGH]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome fans based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="fan",
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

    @property
    def _supports_speed_levels(self) -> bool:
        api_version = self._api_version
        return api_version.major == 1 and api_version.minor > 3

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self._async_set_percentage(percentage)

    async def _async_set_percentage(self, percentage: int | None) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return

        data: dict[str, Any] = {"key": self._static_info.key, "state": True}
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
        await self._client.fan_command(key=self._static_info.key, state=False)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._client.fan_command(
            key=self._static_info.key, oscillating=oscillating
        )

    async def async_set_direction(self, direction: str) -> None:
        """Set direction of the fan."""
        await self._client.fan_command(
            key=self._static_info.key, direction=_FAN_DIRECTIONS.from_hass(direction)
        )

    @property
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the entity is on."""
        return self._state.state

    @property
    @esphome_state_property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self._static_info.supports_speed:
            return None

        if not self._supports_speed_levels:
            return ordered_list_item_to_percentage(
                ORDERED_NAMED_FAN_SPEEDS, self._state.speed  # type: ignore[misc]
            )

        return ranged_value_to_percentage(
            (1, self._static_info.supported_speed_levels), self._state.speed_level
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        if not self._supports_speed_levels:
            return len(ORDERED_NAMED_FAN_SPEEDS)
        return self._static_info.supported_speed_levels

    @property
    @esphome_state_property
    def oscillating(self) -> bool | None:
        """Return the oscillation state."""
        if not self._static_info.supports_oscillation:
            return None
        return self._state.oscillating

    @property
    @esphome_state_property
    def current_direction(self) -> str | None:
        """Return the current fan direction."""
        if not self._static_info.supports_direction:
            return None
        return _FAN_DIRECTIONS.from_esphome(self._state.direction)

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._static_info.supports_oscillation:
            flags |= FanEntityFeature.OSCILLATE
        if self._static_info.supports_speed:
            flags |= FanEntityFeature.SET_SPEED
        if self._static_info.supports_direction:
            flags |= FanEntityFeature.DIRECTION
        return flags
