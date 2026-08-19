"""Support for AirGradient sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from airgradient import Config
from airgradient.models import (
    ConfigurationControl,
    LedBarMode,
    Measures,
    TemperatureUnit,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDensity,
    UnitOfElectricPotential,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AirGradientConfigEntry
from .const import PM_STANDARD, PM_STANDARD_REVERSE, supports_config
from .coordinator import AirGradientCoordinator
from .entity import AirGradientEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirGradientMeasurementSensorEntityDescription(SensorEntityDescription):
    """Describes AirGradient measurement sensor entity."""

    value_fn: Callable[[Measures], StateType]


@dataclass(frozen=True, kw_only=True)
class AirGradientConfigSensorEntityDescription(SensorEntityDescription):
    """Describes AirGradient config sensor entity."""

    config_key: str
    value_fn: Callable[[Config], StateType]


MEASUREMENT_SENSOR_TYPES: tuple[AirGradientMeasurementSensorEntityDescription, ...] = (
    AirGradientMeasurementSensorEntityDescription(
        key="pm01",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm01,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm02",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm02,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm10,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.ambient_temperature,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.relative_humidity,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.signal_strength,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="tvoc",
        translation_key="total_volatile_organic_component_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.total_volatile_organic_component_index,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="nitrogen_index",
        translation_key="nitrogen_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.nitrogen_index,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.rco2,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm003",
        translation_key="pm003_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm003_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm005_count",
        translation_key="pm005_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.pm005_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm01_count",
        translation_key="pm01_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.pm01_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm02_count",
        translation_key="pm02_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.pm02_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm50_count",
        translation_key="pm50_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.pm50_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm10_count",
        translation_key="pm10_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.pm10_count,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="battery_percentage",
        translation_key="battery_percentage",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.battery_percentage,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.battery_voltage,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="charge_voltage",
        translation_key="charge_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.charge_voltage,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="nox_raw",
        translation_key="raw_nitrogen",
        native_unit_of_measurement="ticks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.raw_nitrogen,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="tvoc_raw",
        translation_key="raw_total_volatile_organic_component",
        native_unit_of_measurement="ticks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.raw_total_volatile_organic_component,
    ),
    AirGradientMeasurementSensorEntityDescription(
        key="pm02_raw",
        translation_key="raw_pm02",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.raw_pm02,
    ),
)

CONFIG_SENSOR_TYPES: tuple[AirGradientConfigSensorEntityDescription, ...] = (
    AirGradientConfigSensorEntityDescription(
        key="co2_automatic_baseline_calibration_days",
        translation_key="co2_automatic_baseline_calibration_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="co2_automatic_baseline_calibration_days",
        value_fn=lambda config: config.co2_automatic_baseline_calibration_days,
    ),
    AirGradientConfigSensorEntityDescription(
        key="nox_learning_offset",
        translation_key="nox_learning_offset",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="nox_learning_offset",
        value_fn=lambda config: config.nox_learning_offset,
    ),
    AirGradientConfigSensorEntityDescription(
        key="tvoc_learning_offset",
        translation_key="tvoc_learning_offset",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="tvoc_learning_offset",
        value_fn=lambda config: config.tvoc_learning_offset,
    ),
)

CONFIG_LED_BAR_SENSOR_TYPES: tuple[AirGradientConfigSensorEntityDescription, ...] = (
    AirGradientConfigSensorEntityDescription(
        key="led_bar_mode",
        translation_key="led_bar_mode",
        device_class=SensorDeviceClass.ENUM,
        options=[x.value for x in LedBarMode],
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="led_bar_mode",
        value_fn=lambda config: config.led_bar_mode,
    ),
    AirGradientConfigSensorEntityDescription(
        key="led_bar_brightness",
        translation_key="led_bar_brightness",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="led_bar_brightness",
        value_fn=lambda config: config.led_bar_brightness,
    ),
)

CONFIG_DISPLAY_SENSOR_TYPES: tuple[AirGradientConfigSensorEntityDescription, ...] = (
    AirGradientConfigSensorEntityDescription(
        key="display_temperature_unit",
        translation_key="display_temperature_unit",
        device_class=SensorDeviceClass.ENUM,
        options=[x.value for x in TemperatureUnit],
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="temperature_unit",
        value_fn=lambda config: config.temperature_unit,
    ),
    AirGradientConfigSensorEntityDescription(
        key="display_pm_standard",
        translation_key="display_pm_standard",
        device_class=SensorDeviceClass.ENUM,
        options=list(PM_STANDARD_REVERSE),
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="pm_standard",
        value_fn=lambda config: (
            PM_STANDARD.get(config.pm_standard) if config.pm_standard else None
        ),
    ),
    AirGradientConfigSensorEntityDescription(
        key="display_brightness",
        translation_key="display_brightness",
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        config_key="display_brightness",
        value_fn=lambda config: config.display_brightness,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirGradientConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AirGradient sensor entities based on a config entry."""

    coordinator = entry.runtime_data
    listener: Callable[[], None] | None = None
    not_setup: set[AirGradientMeasurementSensorEntityDescription] = set(
        MEASUREMENT_SENSOR_TYPES
    )

    @callback
    def add_entities() -> None:
        """Add new entities based on the latest data."""
        nonlocal not_setup, listener
        sensor_descriptions = not_setup
        not_setup = set()
        sensors = []
        for description in sensor_descriptions:
            if description.value_fn(coordinator.data.measures) is None:
                not_setup.add(description)
            else:
                sensors.append(AirGradientMeasurementSensor(coordinator, description))

        if sensors:
            async_add_entities(sensors)
        if not_setup:
            if not listener:
                listener = coordinator.async_add_listener(add_entities)
        elif listener:
            listener()

    add_entities()

    config = coordinator.data.config
    model = coordinator.data.measures.model
    entities = [
        AirGradientConfigSensor(coordinator, description)
        for description in (
            CONFIG_SENSOR_TYPES
            + CONFIG_LED_BAR_SENSOR_TYPES
            + CONFIG_DISPLAY_SENSOR_TYPES
        )
        if supports_config(
            model, coordinator.client.api_version, config, description.config_key
        )
    ]
    async_add_entities(entities)


class AirGradientSensor(AirGradientEntity, SensorEntity):
    """Defines an AirGradient sensor."""

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize airgradient sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"


class AirGradientMeasurementSensor(AirGradientSensor):
    """Defines an AirGradient sensor."""

    entity_description: AirGradientMeasurementSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.measures)


class AirGradientConfigSensor(AirGradientSensor):
    """Defines an AirGradient sensor."""

    entity_description: AirGradientConfigSensorEntityDescription

    def __init__(
        self,
        coordinator: AirGradientCoordinator,
        description: AirGradientConfigSensorEntityDescription,
    ) -> None:
        """Initialize airgradient sensor."""
        super().__init__(coordinator, description)
        self._attr_entity_registry_enabled_default = (
            coordinator.data.config.configuration_control
            is not ConfigurationControl.LOCAL
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.config)
