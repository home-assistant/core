"""Fan platform for Prana integration."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Any

from prana_local_api_client.models.prana_state import FanState

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

from .coordinator import PranaConfigEntry, PranaCoordinator
from .entity import PranaBaseEntity

PARALLEL_UPDATES = 1

# The device API expects speeds in tenths of a step.
PRANA_SPEED_MULTIPLIER = 10

PRESET_AUTO = "auto"
PRESET_AUTO_PLUS = "auto_plus"
PRESET_NIGHT = "night"
PRESET_BOOST = "boost"

PRESET_MODES = [
    PRESET_AUTO,
    PRESET_AUTO_PLUS,
    PRESET_NIGHT,
    PRESET_BOOST,
]


class PranaFanType(StrEnum):
    """Target fan on the Prana API."""

    SUPPLY = "supply"
    EXTRACT = "extract"
    VENTILATION = "bounded"


@dataclass(frozen=True, kw_only=True)
class PranaFanEntityDescription(FanEntityDescription):
    """Description of a Prana fan entity."""

    key: str
    api_target: PranaFanType
    value_fn: Callable[[PranaCoordinator], FanState]


VENTILATION_DESCRIPTION = PranaFanEntityDescription(
    key="ventilation",
    translation_key="ventilation",
    api_target=PranaFanType.VENTILATION,
    name=None,
    value_fn=lambda coord: coord.data.bounded,
)

SPLIT_DESCRIPTIONS: tuple[PranaFanEntityDescription, ...] = (
    PranaFanEntityDescription(
        key="supply",
        translation_key="supply",
        api_target=PranaFanType.SUPPLY,
        value_fn=lambda coord: coord.data.supply,
    ),
    PranaFanEntityDescription(
        key="extract",
        translation_key="extract",
        api_target=PranaFanType.EXTRACT,
        value_fn=lambda coord: coord.data.extract,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana fan entities from a config entry."""
    coordinator = entry.runtime_data
    # Whether supply and extract fans are physically linked is a device
    # capability reported in state: linked models expose one ventilation fan,
    # split models expose independent supply and extract fans.
    if coordinator.data.bound:
        descriptions: tuple[PranaFanEntityDescription, ...] = (VENTILATION_DESCRIPTION,)
    else:
        descriptions = SPLIT_DESCRIPTIONS
    async_add_entities(
        PranaFan(coordinator, description) for description in descriptions
    )


class PranaFan(PranaBaseEntity, FanEntity):
    """Representation of a Prana fan entity."""

    entity_description: PranaFanEntityDescription
    _attr_preset_modes = PRESET_MODES
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )

    @property
    def _speed_range(self) -> tuple[int, int]:
        return (1, self.entity_description.value_fn(self.coordinator).max_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed percentage."""
        current_speed = self.entity_description.value_fn(self.coordinator).speed
        return ranged_value_to_percentage(self._speed_range, current_speed)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed (0-100%) by converting to device speed steps."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self.coordinator.api_client.set_speed(
            math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
            * PRANA_SPEED_MULTIPLIER,
            self.entity_description.api_target,
        )
        await self.coordinator.async_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if the fan is on."""
        return self.entity_description.value_fn(self.coordinator).is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the fan on and optionally set speed or preset mode."""
        if percentage == 0:
            await self.async_turn_off()
            return

        await self.coordinator.api_client.set_speed_is_on(
            True, self.entity_description.api_target
        )
        if percentage is not None:
            await self.async_set_percentage(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is None and preset_mode is None:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.coordinator.api_client.set_speed_is_on(
            False, self.entity_description.api_target
        )
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Activate a preset mode on the device.

        Prana operating modes (auto/auto_plus/night/boost/winter) are
        mutually exclusive on the device: activating one clears the rest.
        """
        await self.coordinator.api_client.set_switch(preset_mode, True)
        await self.coordinator.async_refresh()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode, if any."""
        data = self.coordinator.data
        for preset in PRESET_MODES:
            if getattr(data, preset, False):
                return preset
        return None
