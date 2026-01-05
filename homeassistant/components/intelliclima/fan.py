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

PRESET_MODES_TO_INTELLICLIMA_MODE = {
    "forward": str(FanMode.inward),
    "reverse": str(FanMode.outward),
    "alternate": str(FanMode.alternate),
    "sensor": str(FanMode.sensor),
    "auto": str(FanMode.sensor),
}
INTELLICLIMA_MODE_TO_PRESET_MODES = {
    v: k for k, v in PRESET_MODES_TO_INTELLICLIMA_MODE.items() if k != "auto"
}


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
        return self._device_data.mode_set != FanMode.off

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

        return INTELLICLIMA_MODE_TO_PRESET_MODES[device_data.mode_set]

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return list(PRESET_MODES_TO_INTELLICLIMA_MODE.keys())

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
        await self.async_set_mode_speed(preset_mode=preset_mode, percentage=percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.api.ecocomfort.turn_off(self._device_sn)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        preset_mode = "alternate" if self.preset_mode == "auto" else self.preset_mode
        return await self.async_set_mode_speed(
            preset_mode=preset_mode, percentage=percentage
        )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        return await self.async_set_mode_speed(preset_mode=preset_mode)

    async def async_set_mode_speed(
        self, preset_mode: str | None = None, percentage: int | None = None
    ) -> None:
        """Set mode and speed.

        If preset_mode or percentage are None, it first defaults to the respective property.
        If that is also None, then preset_mode defaults to 'alternate' and percentage to 25 (sleep)
        """
        preset_mode = self.preset_mode if preset_mode is None else preset_mode
        percentage = self.percentage if percentage is None else percentage

        preset_mode = "alternate" if preset_mode is None else preset_mode
        percentage = 25 if percentage is None else percentage

        if preset_mode == "auto":
            # auto is a special case with special mode and speed setting
            await self.coordinator.api.ecocomfort.set_mode_speed_auto(self._device_sn)
            return await self.coordinator.async_request_refresh()

        if percentage == 0:
            # Setting fan speed to zero turns off the fan
            return await self.async_turn_off()

        mode = PRESET_MODES_TO_INTELLICLIMA_MODE[preset_mode]
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
        return await self.coordinator.async_request_refresh()
