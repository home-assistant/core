"""Number platform for Liebherr integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyliebherrhomeapi import TemperatureControl, TemperatureUnit

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LiebherrConfigEntry, LiebherrCoordinator
from .entity import LiebherrZoneEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class LiebherrNumberEntityDescription(NumberEntityDescription):
    """Describes Liebherr number entity."""

    value_fn: Callable[[TemperatureControl], float | None]
    min_fn: Callable[[TemperatureControl], float | None]
    max_fn: Callable[[TemperatureControl], float | None]
    unit_fn: Callable[[TemperatureControl], str]


NUMBER_TYPES: tuple[LiebherrNumberEntityDescription, ...] = (
    LiebherrNumberEntityDescription(
        key="setpoint_temperature",
        translation_key="setpoint_temperature",
        device_class=NumberDeviceClass.TEMPERATURE,
        native_step=1,
        value_fn=lambda control: control.target,
        min_fn=lambda control: control.min,
        max_fn=lambda control: control.max,
        unit_fn=lambda control: (
            UnitOfTemperature.FAHRENHEIT
            if control.unit == TemperatureUnit.FAHRENHEIT
            else UnitOfTemperature.CELSIUS
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LiebherrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Liebherr number entities."""
    coordinators = entry.runtime_data
    async_add_entities(
        LiebherrNumber(
            coordinator=coordinator,
            zone_id=temp_control.zone_id,
            description=description,
        )
        for coordinator in coordinators.values()
        for temp_control in coordinator.data.get_temperature_controls().values()
        for description in NUMBER_TYPES
    )


class LiebherrNumber(LiebherrZoneEntity, NumberEntity):
    """Representation of a Liebherr number entity."""

    entity_description: LiebherrNumberEntityDescription

    def __init__(
        self,
        coordinator: LiebherrCoordinator,
        zone_id: int,
        description: LiebherrNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, zone_id)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}_{zone_id}"

        # If device has only one zone, use translation key without zone suffix
        temp_controls = coordinator.data.get_temperature_controls()
        if len(temp_controls) > 1 and (zone_key := self._get_zone_translation_key()):
            self._attr_translation_key = f"{description.translation_key}_{zone_key}"

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        if (temp_control := self.temperature_control) is None:
            return None
        return self.entity_description.unit_fn(temp_control)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if TYPE_CHECKING:
            assert self.temperature_control is not None
        return self.entity_description.value_fn(self.temperature_control)

    @property
    def native_min_value(self) -> float:
        """Return the minimum value."""
        if (temp_control := self.temperature_control) is None:
            return DEFAULT_MIN_VALUE
        if (min_val := self.entity_description.min_fn(temp_control)) is None:
            return DEFAULT_MIN_VALUE
        return min_val

    @property
    def native_max_value(self) -> float:
        """Return the maximum value."""
        if (temp_control := self.temperature_control) is None:
            return DEFAULT_MAX_VALUE
        if (max_val := self.entity_description.max_fn(temp_control)) is None:
            return DEFAULT_MAX_VALUE
        return max_val

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.temperature_control is not None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if TYPE_CHECKING:
            assert self.temperature_control is not None
        temp_control = self.temperature_control

        unit = (
            TemperatureUnit.FAHRENHEIT
            if temp_control.unit == TemperatureUnit.FAHRENHEIT
            else TemperatureUnit.CELSIUS
        )

        await self._async_send_command(
            self.coordinator.client.set_temperature(
                device_id=self.coordinator.device_id,
                zone_id=self._zone_id,
                target=int(value),
                unit=unit,
            ),
        )
