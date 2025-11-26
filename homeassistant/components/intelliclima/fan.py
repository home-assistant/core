"""Fan platform for IntelliClima VMC."""

from dataclasses import dataclass
import math
from typing import Any

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import (
    FAN_MODE_ALTERNATE,
    FAN_MODE_IN,
    FAN_MODE_OFF,
    FAN_MODE_OUT,
    FAN_MODE_SENSOR,
    FAN_SPEED_AUTO,
    FAN_SPEED_HIGH,
    FAN_SPEED_OFF,
    FAN_SPEED_SLEEP,
)
from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity

PRESET_MODES_TO_INTELLICLIMA_MODE = {
    "forward": FAN_MODE_IN,
    "reverse": FAN_MODE_OUT,
    "alternate": FAN_MODE_ALTERNATE,
    "sensor": FAN_MODE_SENSOR,
    "auto": FAN_MODE_SENSOR,
}
INTELLICLIMA_MODE_TO_PRESET_MODES = {
    v: k for k, v in PRESET_MODES_TO_INTELLICLIMA_MODE.items() if k != "auto"
}


@dataclass(frozen=True)
class IntelliClimaFanRequiredKeysMixin:
    """Required keys for fan entity."""

    speed_range: tuple[int, int]


@dataclass(frozen=True)
class IntelliClimaFanEntityDescription(
    FanEntityDescription, IntelliClimaFanRequiredKeysMixin
):
    """Describes a fan entity."""


INTELLICLIMA_FANS: tuple[IntelliClimaFanEntityDescription, ...] = (
    IntelliClimaFanEntityDescription(
        key="fan",
        translation_key="fan",
        speed_range=(int(FAN_SPEED_SLEEP), int(FAN_SPEED_HIGH)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IntelliClima VMC fans."""
    coordinator: IntelliClimaCoordinator = entry.runtime_data

    entities: list[IntelliClimaVMCFan] = []
    for ecocomfort2 in coordinator.data.ecocomfort2.values():
        entities.extend(
            IntelliClimaVMCFan(
                coordinator=coordinator, device=ecocomfort2, description=description
            )
            for description in INTELLICLIMA_FANS
        )

    async_add_entities(entities)


class IntelliClimaVMCFan(IntelliClimaECOEntity, FanEntity):
    """Representation of an IntelliClima VMC fan."""

    entity_description: IntelliClimaFanEntityDescription
    _attr_supported_features = (
        FanEntityFeature.PRESET_MODE
        | FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False
        return self._device_id in self.coordinator.data.ecocomfort2

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return (
            self.coordinator.data.ecocomfort2[self._device_id].mode_set != FAN_MODE_OFF
        )

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        device_data = self.coordinator.data.ecocomfort2[self._device_id]

        if device_data.speed_set == FAN_SPEED_AUTO:
            return None

        return ranged_value_to_percentage(
            self.entity_description.speed_range, int(device_data.speed_set)
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self.entity_description.speed_range)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        device_data = self.coordinator.data.ecocomfort2[self._device_id]

        if device_data.mode_set == FAN_MODE_OFF:
            return None
        if (
            device_data.speed_set == FAN_SPEED_AUTO
            and device_data.mode_set == FAN_MODE_SENSOR
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
        return await self.async_set_mode_speed(percentage=percentage)

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
            mode = FAN_MODE_SENSOR
            speed = FAN_SPEED_AUTO
        elif percentage == 0:
            # Setting fan speed to zero turns off the fan
            return await self.async_turn_off()
        else:
            mode = PRESET_MODES_TO_INTELLICLIMA_MODE[preset_mode]
            speed = str(
                math.ceil(
                    percentage_to_ranged_value(
                        self.entity_description.speed_range,
                        percentage,
                    )
                )
            )

        speed = FAN_SPEED_SLEEP if speed == FAN_SPEED_OFF else speed
        await self.coordinator.api.ecocomfort.set_mode_speed(
            self._device_sn, mode, speed
        )
        return await self.coordinator.async_request_refresh()
