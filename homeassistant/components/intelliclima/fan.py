"""Fan platform for IntelliClima VMC."""

import math
from typing import Any

from pyintelliclima.const import FanMode, FanSpeed
from pyintelliclima.intelliclima_types import IntelliClimaECO

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
    coordinator = entry.runtime_data

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
        device: IntelliClimaECO,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._speed_range = (int(FanSpeed.sleep), int(FanSpeed.high))

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return bool(self._device_data.mode_set != FanMode.off)

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        device_data = self._device_data

        if device_data.speed_set == FanSpeed.auto:
            return None

        return ranged_value_to_percentage(self._speed_range, int(device_data.speed_set))

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        device_data = self._device_data

        if device_data.mode_set == FanMode.off:
            return None
        if (
            device_data.speed_set == FanSpeed.auto
            and device_data.mode_set == FanMode.sensor
        ):
            return "auto"

        return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan.

        Defaults back to 25% if percentage argument is 0 to prevent loop of turning off/on
        infinitely.
        """
        percentage = 25 if percentage == 0 else percentage
        await self.async_set_mode_speed(fan_mode=preset_mode, percentage=percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.api.ecocomfort.turn_off(self._device_sn)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        await self.async_set_mode_speed(percentage=percentage)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        await self.async_set_mode_speed(fan_mode=preset_mode)

    async def async_set_mode_speed(
        self, fan_mode: str | None = None, percentage: int | None = None
    ) -> None:
        """Set mode and speed.

        If percentage is None, it first defaults to the respective property.
        If that is also None, then percentage defaults to 25 (sleep)
        """
        percentage = self.percentage if percentage is None else percentage
        percentage = 25 if percentage is None else percentage

        if fan_mode == "auto":
            # auto is a special case with special mode and speed setting
            await self.coordinator.api.ecocomfort.set_mode_speed_auto(self._device_sn)
            await self.coordinator.async_request_refresh()
            return
        if percentage == 0:
            # Setting fan speed to zero turns off the fan
            await self.async_turn_off()
            return

        # Determine the fan mode
        if fan_mode is not None:
            # Set to requested fan_mode
            mode = fan_mode
        elif not self.is_on:
            # Default to alternate fan mode if not turned on
            mode = FanMode.alternate
        else:
            # Maintain current mode
            mode = self._device_data.mode_set

        speed = str(
            math.ceil(
                percentage_to_ranged_value(
                    self._speed_range,
                    percentage,
                )
            )
        )

        speed = FanSpeed.sleep if speed == FanSpeed.off else speed
        await self.coordinator.api.ecocomfort.set_mode_speed(
            self._device_sn, mode, speed
        )
        await self.coordinator.async_request_refresh()
