"""Support for ESPHome fans."""
from typing import List, Optional

from aioesphomeapi import FanInfo, FanSpeed, FanState

from homeassistant.components.fan import (
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    EsphomeEntity,
    esphome_map_enum,
    esphome_state_property,
    platform_async_setup_entry,
)


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


@esphome_map_enum
def _fan_speeds():
    return {
        FanSpeed.LOW: SPEED_LOW,
        FanSpeed.MEDIUM: SPEED_MEDIUM,
        FanSpeed.HIGH: SPEED_HIGH,
    }


class EsphomeFan(EsphomeEntity, FanEntity):
    """A fan implementation for ESPHome."""

    @property
    def _static_info(self) -> FanInfo:
        return super()._static_info

    @property
    def _state(self) -> Optional[FanState]:
        return super()._state

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
            return

        await self._client.fan_command(
            self._static_info.key, speed=_fan_speeds.from_hass(speed)
        )

    async def async_turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
            return
        data = {"key": self._static_info.key, "state": True}
        if speed is not None:
            data["speed"] = _fan_speeds.from_hass(speed)
        await self._client.fan_command(**data)

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
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if not self._static_info.supports_speed:
            return None
        return _fan_speeds.from_esphome(self._state.speed)

    @esphome_state_property
    def oscillating(self) -> None:
        """Return the oscillation state."""
        if not self._static_info.supports_oscillation:
            return None
        return self._state.oscillating

    @property
    def speed_list(self) -> Optional[List[str]]:
        """Get the list of available speeds."""
        if not self._static_info.supports_speed:
            return None
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._static_info.supports_oscillation:
            flags |= SUPPORT_OSCILLATE
        if self._static_info.supports_speed:
            flags |= SUPPORT_SET_SPEED
        return flags
