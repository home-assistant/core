"""Fan platform for IntelliClima VMC."""

from dataclasses import dataclass
import math
from typing import Any

from pyintelliclima import IntelliClimaECO

from homeassistant.components.fan import (
    FanEntity,
    FanEntityDescription,
    FanEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
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
    "off": FAN_MODE_OFF,
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

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO,
        description: EntityDescription,
    ) -> None:
        """Initialize the fan."""
        super().__init__(coordinator, device, description)

        self._speed = device.speed_set
        self._mode = device.mode_set

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        if self._device_id not in self.coordinator.data.ecocomfort2:
            return False

        device_data: IntelliClimaECO = self.coordinator.data.ecocomfort2[
            self._device_id
        ]
        return device_data.mode_set != FAN_MODE_OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device_id not in self.coordinator.data.ecocomfort2:
            return None

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
        if self._device_id not in self.coordinator.data.ecocomfort2:
            return None

        device_data = self.coordinator.data.ecocomfort2[self._device_id]
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
        """Turn on the fan."""
        if percentage in (None, 0):
            # default to sleep speed
            percentage = 25

        self._speed = str(
            math.ceil(
                percentage_to_ranged_value(
                    self.entity_description.speed_range,
                    percentage,  # type: ignore[arg-type]
                )
            )
        )

        if preset_mode in (None, "off"):
            # default to alternate mode
            preset_mode = "alternate"

        await self.async_set_preset_mode(preset_mode)  # type: ignore[arg-type]

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        await self.coordinator.api.ecocomfort.turn_off(self._device_sn)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage."""
        # Find closest speed
        self._speed = str(
            math.ceil(
                percentage_to_ranged_value(
                    self.entity_description.speed_range, percentage
                )
            )
        )

        if self._speed == FAN_SPEED_OFF:
            return await self.async_turn_off()

        await self.async_set_mode_speed()
        return None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set preset mode."""
        self._mode = PRESET_MODES_TO_INTELLICLIMA_MODE[preset_mode]
        if preset_mode == "auto":
            self._speed = FAN_SPEED_AUTO
            await self.async_set_mode_speed_auto()
        elif preset_mode == "off":
            self._speed = FAN_SPEED_OFF
            await self.async_turn_off()
        else:
            self._speed = (
                FAN_SPEED_SLEEP if self._speed == FAN_SPEED_AUTO else self._speed
            )  # need to set speed to non-auto mode, defaulting to sleep speed
            await self.async_set_mode_speed()

    async def async_set_mode_speed(self) -> None:
        """Set mode and speed.

        Checks if mode is not set to 'off'. If so, defaults back to 'alternate'.
        Checks if speed is not set to 'off', If so, defaults back to 'sleep'.
        Turning off has a separate, different api call.
        """
        self._mode = FAN_MODE_ALTERNATE if self._mode == FAN_MODE_OFF else self._mode
        self._speed = FAN_SPEED_SLEEP if self._speed == FAN_SPEED_OFF else self._speed
        await self.coordinator.api.ecocomfort.set_mode_speed(
            self._device_sn, self._mode, self._speed
        )
        await self.coordinator.async_request_refresh()

    async def async_set_mode_speed_auto(self) -> None:
        """Set mode and speed for the 'auto' preset-mode."""
        await self.coordinator.api.ecocomfort.set_mode_speed_auto(self._device_sn)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
