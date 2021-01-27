"""Support for ESPHome fans."""
from typing import Optional

from aioesphomeapi import FanInfo, FanSpeed, FanState

from homeassistant.components.fan import SUPPORT_OSCILLATE, SUPPORT_SET_SPEED, FanEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry

ORDERED_NAMED_FAN_SPEEDS = [FanSpeed.LOW, FanSpeed.MEDIUM, FanSpeed.HIGH]


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
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


class EsphomeFan(EsphomeEntity, FanEntity):
    """A fan implementation for ESPHome."""

    @property
    def _static_info(self) -> FanInfo:
        return super()._static_info

    @property
    def _state(self) -> Optional[FanState]:
        return super()._state

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        if percentage == 0:
            await self.async_turn_off()
            return

        data = {"key": self._static_info.key, "state": True}
        if percentage is not None:
            named_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )
            data["speed"] = named_speed
        await self._client.fan_command(**data)

    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._client.fan_command(key=self._static_info.key, state=False)

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self._client.fan_command(
            key=self._static_info.key, oscillating=oscillating
        )

    # https://github.com/PyCQA/pylint/issues/3150 for all @esphome_state_property
    # pylint: disable=invalid-overridden-method

    @esphome_state_property
    def is_on(self) -> Optional[bool]:
        """Return true if the entity is on."""
        return self._state.state

    @esphome_state_property
    def percentage(self) -> Optional[str]:
        """Return the current speed percentage."""
        if not self._static_info.supports_speed:
            return None
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._state.speed
        )

    @esphome_state_property
    def oscillating(self) -> None:
        """Return the oscillation state."""
        if not self._static_info.supports_oscillation:
            return None
        return self._state.oscillating

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._static_info.supports_oscillation:
            flags |= SUPPORT_OSCILLATE
        if self._static_info.supports_speed:
            flags |= SUPPORT_SET_SPEED
        return flags
