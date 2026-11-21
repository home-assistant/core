"""Support for Vallox ventilation unit sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time
from typing import override

from vallox_websocket_api import MetricData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_NAME,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .const import (
    METRIC_KEY_MODE,
    MODE_ON,
    PRESET_MODE_TO_VALLOX_PROFILE,
    VALLOX_CELL_STATE_TO_STR,
    VALLOX_PROFILE_TO_PRESET_MODE,
)
from .coordinator import ValloxConfigEntry, ValloxDataUpdateCoordinator
from .entity import ValloxEntity


@dataclass(frozen=True, kw_only=True)
class ValloxMetricSensorEntityDescription(SensorEntityDescription):
    """Describes a Vallox sensor that reports a single metric."""

    metric_key: str


@dataclass(frozen=True, kw_only=True)
class ValloxComputedSensorEntityDescription(SensorEntityDescription):
    """Describes a Vallox sensor whose value is computed from the metrics."""

    value_fn: Callable[[MetricData], StateType | datetime]


class ValloxSensorEntity(ValloxEntity, SensorEntity):
    """Representation of a Vallox sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(name, coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"


class ValloxMetricSensorEntity(ValloxSensorEntity):
    """Representation of a Vallox sensor that reports a single metric."""

    entity_description: ValloxMetricSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.get(self.entity_description.metric_key)


class ValloxComputedSensorEntity(ValloxSensorEntity):
    """Representation of a Vallox sensor whose value is computed from the metrics."""

    entity_description: ValloxComputedSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)


def _fan_speed(data: MetricData, metric_key: str) -> StateType:
    """Return a fan speed, or 0 while the unit is off."""
    if (mode := data.get(METRIC_KEY_MODE)) is None:
        return None
    # The unit keeps reporting its last fan speeds after it is turned off.
    return data.get(metric_key) if mode == MODE_ON else 0


def _next_filter_change(data: MetricData) -> datetime | None:
    """Return when the filter is due for a change."""
    if (next_filter_change_date := data.next_filter_change_date) is None:
        return None

    return datetime.combine(
        next_filter_change_date,
        time(hour=13, minute=0, second=0, tzinfo=dt_util.get_default_time_zone()),
    )


def _cell_state(data: MetricData) -> str | None:
    """Return the name of the cell state."""
    if not isinstance(cell_state := data.get("A_CYC_CELL_STATE"), int):
        return None
    return VALLOX_CELL_STATE_TO_STR.get(cell_state)


METRIC_SENSOR_ENTITIES: tuple[ValloxMetricSensorEntityDescription, ...] = (
    ValloxMetricSensorEntityDescription(
        key="extract_air",
        translation_key="extract_air",
        metric_key="A_CYC_TEMP_EXTRACT_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxMetricSensorEntityDescription(
        key="exhaust_air",
        translation_key="exhaust_air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxMetricSensorEntityDescription(
        key="outdoor_air",
        translation_key="outdoor_air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxMetricSensorEntityDescription(
        key="supply_air",
        translation_key="supply_air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxMetricSensorEntityDescription(
        key="supply_cell_air",
        translation_key="supply_cell_air",
        metric_key="A_CYC_TEMP_SUPPLY_CELL_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxMetricSensorEntityDescription(
        key="optional_air",
        translation_key="optional_air",
        metric_key="A_CYC_TEMP_OPTIONAL",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    ValloxMetricSensorEntityDescription(
        key="humidity",
        metric_key="A_CYC_RH_VALUE",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
    ),
    ValloxMetricSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        metric_key="A_CYC_EXTRACT_EFFICIENCY",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    ValloxMetricSensorEntityDescription(
        key="co2",
        metric_key="A_CYC_CO2_VALUE",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
    ),
)

COMPUTED_SENSOR_ENTITIES: tuple[ValloxComputedSensorEntityDescription, ...] = (
    ValloxComputedSensorEntityDescription(
        key="current_profile",
        translation_key="current_profile",
        device_class=SensorDeviceClass.ENUM,
        options=list(PRESET_MODE_TO_VALLOX_PROFILE),
        value_fn=lambda data: VALLOX_PROFILE_TO_PRESET_MODE.get(data.profile),
    ),
    ValloxComputedSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        value_fn=lambda data: _fan_speed(data, "A_CYC_FAN_SPEED"),
    ),
    ValloxComputedSensorEntityDescription(
        key="extract_fan_speed",
        translation_key="extract_fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _fan_speed(data, "A_CYC_EXTR_FAN_SPEED"),
    ),
    ValloxComputedSensorEntityDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _fan_speed(data, "A_CYC_SUPP_FAN_SPEED"),
    ),
    ValloxComputedSensorEntityDescription(
        key="remaining_time_for_filter",
        translation_key="remaining_time_for_filter",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_filter_change,
    ),
    ValloxComputedSensorEntityDescription(
        key="cell_state",
        translation_key="cell_state",
        device_class=SensorDeviceClass.ENUM,
        options=list(VALLOX_CELL_STATE_TO_STR.values()),
        value_fn=_cell_state,
    ),
    ValloxComputedSensorEntityDescription(
        key="profile_duration",
        translation_key="profile_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda data: data.get_remaining_profile_duration(data.profile),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ValloxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    name = entry.data[CONF_NAME]
    coordinator = entry.runtime_data

    async_add_entities(
        [
            *(
                ValloxMetricSensorEntity(name, coordinator, description)
                for description in METRIC_SENSOR_ENTITIES
            ),
            *(
                ValloxComputedSensorEntity(name, coordinator, description)
                for description in COMPUTED_SENSOR_ENTITIES
            ),
        ]
    )
