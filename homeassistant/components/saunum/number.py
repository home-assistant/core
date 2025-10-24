"""Number platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import (
    DEFAULT_DURATION,
    DEFAULT_FAN_DURATION,
    DEFAULT_TEMPERATURE_C,
    MAX_DURATION,
    MAX_FAN_DURATION,
    MIN_DURATION,
    MIN_FAN_DURATION,
    MIN_TEMPERATURE_C,
    REG_FAN_DURATION,
    REG_SAUNA_DURATION,
    REG_TARGET_TEMPERATURE,
)
from .entity import LeilSaunaEntity
from .helpers import (
    convert_temperature,
    get_temperature_range_for_unit,
    get_temperature_unit,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LeilSaunaNumberEntityDescription(NumberEntityDescription):
    """Describes Saunum Leil Sauna number entity."""

    register: int
    value_fn: Callable[[dict[str, Any]], int | float | None]


NUMBERS: tuple[LeilSaunaNumberEntityDescription, ...] = (
    LeilSaunaNumberEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        native_step=1,
        icon="mdi:thermometer-high",
        register=REG_TARGET_TEMPERATURE,
        value_fn=lambda data: (
            temp
            if (temp := data.get("target_temperature")) is not None
            and temp >= MIN_TEMPERATURE_C
            else DEFAULT_TEMPERATURE_C
        ),
    ),
    LeilSaunaNumberEntityDescription(
        key="sauna_duration",
        translation_key="sauna_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=MIN_DURATION,
        native_max_value=MAX_DURATION,
        native_step=5,
        icon="mdi:clock-edit-outline",
        register=REG_SAUNA_DURATION,
        value_fn=lambda data: (
            duration
            if (duration := data.get("sauna_duration")) is not None
            and duration > MIN_DURATION
            else DEFAULT_DURATION
        ),
    ),
    LeilSaunaNumberEntityDescription(
        key="fan_duration",
        translation_key="fan_duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=MIN_FAN_DURATION,
        native_max_value=MAX_FAN_DURATION,
        native_step=1,
        icon="mdi:fan-clock",
        register=REG_FAN_DURATION,
        value_fn=lambda data: (
            fan_dur
            if (fan_dur := data.get("fan_duration")) is not None
            and fan_dur > MIN_FAN_DURATION
            else DEFAULT_FAN_DURATION
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna number entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaNumber(coordinator, description) for description in NUMBERS
    )


class LeilSaunaNumber(LeilSaunaEntity, NumberEntity):
    """Representation of a Saunum Leil Sauna number entity."""

    entity_description: LeilSaunaNumberEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

        # Set temperature-specific attributes for target temperature
        if description.key == "target_temperature":
            temp_unit = get_temperature_unit(coordinator.hass)
            min_temp, max_temp, _default_temp = get_temperature_range_for_unit(
                temp_unit
            )
            self._attr_native_unit_of_measurement = temp_unit
            self._attr_native_min_value = min_temp
            self._attr_native_max_value = max_temp

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        value = self.entity_description.value_fn(self.coordinator.data)

        # Convert temperature if needed
        if self.entity_description.key == "target_temperature" and value is not None:
            temp_unit = get_temperature_unit(self.hass)
            value = convert_temperature(
                float(value), UnitOfTemperature.CELSIUS, temp_unit
            )

        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        # Prevent changing certain settings when session is active
        session_active = self.coordinator.data.get("session_active", 0)
        if session_active and self.entity_description.key in (
            "sauna_duration",
            "fan_duration",
        ):
            _LOGGER.warning(
                "Cannot change %s while session is active",
                self.entity_description.key,
            )
            return

        # Convert temperature back to Celsius if needed
        if self.entity_description.key == "target_temperature":
            temp_unit = get_temperature_unit(self.hass)
            value = (
                convert_temperature(value, temp_unit, UnitOfTemperature.CELSIUS)
                or value
            )

        await self.coordinator.async_write_register(
            self.entity_description.register, int(value)
        )
