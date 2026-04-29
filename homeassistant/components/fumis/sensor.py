"""Support for Fumis sensor entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fumis import FumisInfo, StoveAlert, StoveError, StoveState, StoveStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from .coordinator import FumisConfigEntry, FumisDataUpdateCoordinator
from .entity import FumisEntity

PARALLEL_UPDATES = 0


def _code_to_state(code: StoveAlert | StoveError | None) -> str | None:
    """Convert a stove alert or error code to a sensor state value.

    Returns "none" when there is no active alert/error, None when the code
    is unknown, or the enum member name in lowercase for known codes.
    """
    if code is None:
        return "none"
    if code.name == "UNKNOWN":
        return None
    return code.name.lower()


def _code_to_attr(code: StoveAlert | StoveError | None) -> dict[str, str | None]:
    """Convert a stove alert or error code to extra state attributes."""
    if code is None or code.name == "UNKNOWN":
        return {"code": None}
    return {"code": code.value}


@dataclass(frozen=True, kw_only=True)
class FumisSensorEntityDescription(SensorEntityDescription):
    """Describes a Fumis sensor entity."""

    attr_fn: Callable[[FumisInfo], dict[str, Any]] | None = None
    has_fn: Callable[[FumisInfo], bool] = lambda _: True
    value_fn: Callable[[FumisInfo], datetime | float | int | str | None]


SENSORS: tuple[FumisSensorEntityDescription, ...] = (
    FumisSensorEntityDescription(
        key="alert",
        translation_key="alert",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "none",
            *(
                alert.name.lower()
                for alert in StoveAlert
                if alert != StoveAlert.UNKNOWN
            ),
        ],
        value_fn=lambda data: _code_to_state(data.controller.stove_alert),
        attr_fn=lambda data: _code_to_attr(data.controller.stove_alert),
    ),
    FumisSensorEntityDescription(
        key="combustion_chamber_temperature",
        translation_key="combustion_chamber_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.controller.combustion_chamber_temperature is not None,
        value_fn=lambda data: data.controller.combustion_chamber_temperature,
    ),
    FumisSensorEntityDescription(
        key="detailed_stove_status",
        translation_key="detailed_stove_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            status.name.lower()
            for status in StoveStatus
            if status != StoveStatus.UNKNOWN
        ],
        value_fn=lambda data: (
            None
            if data.controller.stove_status is StoveStatus.UNKNOWN
            else data.controller.stove_status.name.lower()
        ),
    ),
    FumisSensorEntityDescription(
        key="error",
        translation_key="error",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=[
            "none",
            *(
                error.name.lower()
                for error in StoveError
                if error != StoveError.UNKNOWN
            ),
        ],
        value_fn=lambda data: _code_to_state(data.controller.stove_error),
        attr_fn=lambda data: _code_to_attr(data.controller.stove_error),
    ),
    FumisSensorEntityDescription(
        key="fan_1_speed",
        translation_key="fan_1_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.controller.fan1_speed is not None,
        value_fn=lambda data: data.controller.fan1_speed,
    ),
    FumisSensorEntityDescription(
        key="fan_2_speed",
        translation_key="fan_2_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.controller.fan2_speed is not None,
        value_fn=lambda data: data.controller.fan2_speed,
    ),
    FumisSensorEntityDescription(
        key="fuel_quantity",
        translation_key="fuel_quantity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        has_fn=lambda data: (
            len(data.controller.fuels) > 0
            and data.controller.fuels[0].quantity_percentage is not None
        ),
        value_fn=lambda data: (
            data.controller.fuels[0].quantity_percentage
            if data.controller.fuels
            else None
        ),
    ),
    FumisSensorEntityDescription(
        key="fuel_used",
        translation_key="fuel_used",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.controller.statistic.fuel_quantity_used,
    ),
    FumisSensorEntityDescription(
        key="heating_time",
        translation_key="heating_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.controller.statistic.heating_time.total_seconds(),
    ),
    FumisSensorEntityDescription(
        key="igniter_starts",
        translation_key="igniter_starts",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.controller.statistic.igniter_starts,
    ),
    FumisSensorEntityDescription(
        key="misfires",
        translation_key="misfires",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.controller.statistic.misfires,
    ),
    FumisSensorEntityDescription(
        key="module_temperature",
        translation_key="module_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.unit.temperature is not None,
        value_fn=lambda data: data.unit.temperature,
    ),
    FumisSensorEntityDescription(
        key="overheatings",
        translation_key="overheatings",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.controller.statistic.overheatings,
    ),
    FumisSensorEntityDescription(
        key="power_output",
        translation_key="power_output",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda data: data.controller.power.kw,
    ),
    FumisSensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        has_fn=lambda data: data.controller.pressure is not None,
        value_fn=lambda data: data.controller.pressure,
    ),
    FumisSensorEntityDescription(
        key="stove_status",
        translation_key="stove_status",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in StoveState if state != StoveState.UNKNOWN],
        value_fn=lambda data: (
            None
            if data.controller.state is StoveState.UNKNOWN
            else data.controller.state.value
        ),
    ),
    FumisSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        has_fn=lambda data: data.controller.main_temperature is not None,
        value_fn=lambda data: (
            data.controller.main_temperature.actual
            if data.controller.main_temperature
            else None
        ),
    ),
    FumisSensorEntityDescription(
        key="time_to_service",
        translation_key="time_to_service",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
        has_fn=lambda data: data.controller.time_to_service is not None,
        value_fn=lambda data: data.controller.time_to_service,
    ),
    FumisSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=ignore_variance(
            lambda data: (
                utcnow().replace(microsecond=0) - data.controller.statistic.uptime
            ),
            timedelta(minutes=5),
        ),
    ),
    FumisSensorEntityDescription(
        key="wifi_rssi",
        translation_key="wifi_rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.unit.rssi,
    ),
    FumisSensorEntityDescription(
        key="wifi_signal_strength",
        translation_key="wifi_signal_strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.unit.signal_strength,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FumisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Fumis sensor entities based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        FumisSensorEntity(coordinator=coordinator, description=description)
        for description in SENSORS
        if description.has_fn(coordinator.data)
    )


class FumisSensorEntity(FumisEntity, SensorEntity):
    """Defines a Fumis sensor entity."""

    entity_description: FumisSensorEntityDescription

    def __init__(
        self,
        coordinator: FumisDataUpdateCoordinator,
        description: FumisSensorEntityDescription,
    ) -> None:
        """Initialize the Fumis sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_{description.key}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.attr_fn is None:
            return None
        return self.entity_description.attr_fn(self.coordinator.data)

    @property
    def native_value(self) -> datetime | float | int | str | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
