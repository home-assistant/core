"""Fan platform for IntelliClima VMC."""

import math
from typing import Any, override

from pyintelliclima import FanMode, FanPreset, FanSpeed, FanSpeedState, IntelliClimaECO2

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IntelliClima VMC fans."""
    coordinator = entry.runtime_data.devices_coordinator

    entities: list[IntelliClimaVMCFan] = [
        IntelliClimaVMCFan(
            coordinator=coordinator,
            device=ecocomfort2,
        )
        for ecocomfort2 in coordinator.data.ecocomfort2_devices.values()
    ]

    async_add_entities(entities)


class IntelliClimaVMCFan(IntelliClimaECOEntity, FanEntity):
    """Representation of an IntelliClima VMC fan."""

    _attr_name = None
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_preset_modes = ["auto"]

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._speed_range = (int(FanSpeed.sleep), int(FanSpeed.high))
        self._attr_unique_id = device.id

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if fan is on."""
        if (fan_state := self._fan_state) is None:
            return None
        return fan_state.direction is not FanMode.off

    @property
    @override
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if (fan_state := self._fan_state) is None:
            return None
        if fan_state.speed is FanSpeedState.off:
            return 0
        # Boost runs above the highest speed that can be set.
        return ranged_value_to_percentage(
            self._speed_range, min(fan_state.speed, FanSpeedState.speed3)
        )

    @property
    @override
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    @property
    @override
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        fan_state = self._fan_state
        if fan_state is not None and fan_state.preset is FanPreset.auto:
            return "auto"
        return None

    @override
    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan.

        Defaults back to 25% if percentage argument is 0
        to prevent loop of turning off/on infinitely.
        """
        percentage = 25 if percentage == 0 else percentage
        await self.async_set_mode_speed(preset_mode=preset_mode, percentage=percentage)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.api.ecocomfort2.turn_off(self._device_sn)
        await self.coordinator.async_request_refresh()

    @override
    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        await self.async_set_mode_speed(percentage=percentage)

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.async_set_mode_speed(preset_mode=preset_mode)

    async def async_set_mode_speed(
        self, preset_mode: str | None = None, percentage: int | None = None
    ) -> None:
        """Set mode and speed.

        If percentage is None, it defaults to the last commanded speed.
        If that is off or auto, then percentage defaults to 25 (sleep)
        """
        if percentage is None:
            # Not the running speed: that may be a boost or night override.
            speed_set = self._device_data.speed_set
            percentage = (
                25
                if speed_set in (FanSpeed.off, FanSpeed.auto)
                else ranged_value_to_percentage(self._speed_range, int(speed_set))
            )

        if preset_mode == "auto":
            # auto is a special case with special mode and speed setting
            await self.coordinator.api.ecocomfort2.set_mode_speed_auto(self._device_sn)
            await self.coordinator.async_request_refresh()
            return
        if percentage == 0:
            # Setting fan speed to zero turns off the fan
            await self.async_turn_off()
            return

        # Keep the commanded mode, defaulting to alternate when turned off
        mode = self._device_data.mode_set
        if mode == FanMode.off:
            mode = FanMode.alternate

        speed = FanSpeed(
            str(
                math.ceil(
                    percentage_to_ranged_value(
                        self._speed_range,
                        percentage,
                    )
                )
            )
        )

        speed = FanSpeed.sleep if speed == FanSpeed.off else speed
        await self.coordinator.api.ecocomfort2.set_mode_speed(
            self._device_sn, mode, speed
        )
        await self.coordinator.async_request_refresh()
