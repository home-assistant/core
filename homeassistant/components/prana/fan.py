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

# The Prana device API expects fan speed values in scaled units (tenths of a speed step)
# rather than the raw step value used internally by this integration. This factor is
# applied when sending speeds to the API to match its expected units.
PRANA_SPEED_MULTIPLIER = 10


class PranaFanType(StrEnum):
    """Enumerates Prana fan types exposed by the device API."""

    SUPPLY = "supply"
    EXTRACT = "extract"
    BOUNDED = "bounded"


@dataclass(frozen=True, kw_only=True)
class PranaFanEntityDescription(FanEntityDescription):
    """Description of a Prana fan entity."""

    key: PranaFanType
    value_fn: Callable[[PranaCoordinator], FanState]
    speed_range: Callable[[PranaCoordinator], tuple[int, int]]


ENTITIES: tuple[PranaFanEntityDescription, ...] = (
    PranaFanEntityDescription(
        key=PranaFanType.SUPPLY,
        translation_key="supply",
        value_fn=lambda coord: (
            coord.data.supply if not coord.data.bound else coord.data.bounded
        ),
        speed_range=lambda coord: (
            1,
            coord.data.supply.max_speed
            if not coord.data.bound
            else coord.data.bounded.max_speed,
        ),
    ),
    PranaFanEntityDescription(
        key=PranaFanType.EXTRACT,
        translation_key="extract",
        value_fn=lambda coord: (
            coord.data.extract if not coord.data.bound else coord.data.bounded
        ),
        speed_range=lambda coord: (
            1,
            coord.data.extract.max_speed
            if not coord.data.bound
            else coord.data.bounded.max_speed,
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PranaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Prana fan entities from a config entry."""
    async_add_entities(
        PranaFan(entry.runtime_data, entity_description)
        for entity_description in ENTITIES
    )


class PranaFan(PranaBaseEntity, FanEntity):
    """Representation of a Prana fan entity."""

    entity_description: PranaFanEntityDescription
    _attr_preset_modes = ["night", "boost"]
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.PRESET_MODE
    )

    @property
    def _api_target_key(self) -> str:
        """Return the correct target key for API commands based on bounded state."""
        # If the device is in bound mode, both supply and extract fans control the same bounded fan speeds.
        if self.coordinator.data.bound:
            return PranaFanType.BOUNDED
        # Otherwise, return the specific fan type (supply or extract) for API commands.
        return self.entity_description.key

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(
            self.entity_description.speed_range(self.coordinator)
        )

    @property
    def percentage(self) -> int | None:
        """Return the current fan speed percentage."""
        current_speed = self.entity_description.value_fn(self.coordinator).speed
        return ranged_value_to_percentage(
            self.entity_description.speed_range(self.coordinator), current_speed
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed (0-100%) by converting to device-specific speed steps."""
        if percentage == 0:
            await self.async_turn_off()
            return
        await self.coordinator.api_client.set_speed(
            math.ceil(
                percentage_to_ranged_value(
                    self.entity_description.speed_range(self.coordinator),
                    percentage,
                )
            )
            * PRANA_SPEED_MULTIPLIER,
            self._api_target_key,
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

        await self.coordinator.api_client.set_speed_is_on(True, self._api_target_key)
        if percentage is not None:
            await self.async_set_percentage(percentage)
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        if percentage is None and preset_mode is None:
            await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self.coordinator.api_client.set_speed_is_on(False, self._api_target_key)
        await self.coordinator.async_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode (e.g., night or boost)."""
        await self.coordinator.api_client.set_switch(preset_mode, True)
        await self.coordinator.async_refresh()

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        if self.coordinator.data.night:
            return "night"
        if self.coordinator.data.boost:
            return "boost"
        return None
