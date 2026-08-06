"""Sensor platform for the Tewke integration.

Exposes all numeric fields from the BME680 and ambient light readings,
delivered via CoAP observation (local_push). No polling occurs.

Disabled-by-default sensors are raw/diagnostic values.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfPressure,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import TewkeEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytewke.data import EnergyData, RadarData, SensorData

    from homeassistant.core import HomeAssistant

    from .coordinator import TewkeCoordinator
    from .data import TewkeConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TewkeSensorEntityDescription(SensorEntityDescription):
    """Describes a Tewke sensor entity."""

    value_fn: Callable[[SensorData], float | int | None]


SENSOR_DESCRIPTIONS: tuple[TewkeSensorEntityDescription, ...] = (
    TewkeSensorEntityDescription(
        key="iaq",
        translation_key="iaq",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.iaq,
    ),
    TewkeSensorEntityDescription(
        key="static_iaq",
        translation_key="static_iaq",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.static_iaq,
    ),
    TewkeSensorEntityDescription(
        key="compensated_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.compensated_temperature,
    ),
    TewkeSensorEntityDescription(
        key="compensated_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: (
            round(s.compensated_humidity, 2)
            if s.compensated_humidity is not None
            else None
        ),
    ),
    TewkeSensorEntityDescription(
        key="co2_equivalent",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.co2_equivalent,
    ),
    TewkeSensorEntityDescription(
        key="raw_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PA,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.raw_pressure,
    ),
    TewkeSensorEntityDescription(
        key="gas_percentage",
        translation_key="gas_percentage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.gas_percentage,
    ),
    TewkeSensorEntityDescription(
        key="ambient_light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: (
            round(s.ambient_light.lux, 2) if s.ambient_light is not None else None
        ),
    ),
    # Disabled by default — diagnostic / raw calibration values
    TewkeSensorEntityDescription(
        key="iaq_accuracy",
        translation_key="iaq_accuracy",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.iaq_accuracy,
    ),
    TewkeSensorEntityDescription(
        key="breath_voc_equivalent",
        translation_key="breath_voc_equivalent",
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.breath_voc_equivalent,
    ),
    TewkeSensorEntityDescription(
        key="raw_temperature",
        translation_key="raw_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.raw_temperature,
    ),
    TewkeSensorEntityDescription(
        key="raw_humidity",
        translation_key="raw_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.raw_humidity,
    ),
    TewkeSensorEntityDescription(
        key="raw_gas",
        translation_key="raw_gas",
        native_unit_of_measurement="Ω",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda s: s.raw_gas,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: TewkeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tewke sensor entities from a config entry."""
    coordinator = entry.runtime_data.coordinator
    entities: list[TewkeSensor | TewkeRadarSensor | TewkeEnergySensor] = []

    if coordinator.data.get("sensors") is not None:
        entities.extend(
            TewkeSensor(coordinator=coordinator, description=description)
            for description in SENSOR_DESCRIPTIONS
        )

    if coordinator.data.get("radar") is not None:
        entities.extend(
            TewkeRadarSensor(coordinator=coordinator, description=description)
            for description in RADAR_SENSOR_DESCRIPTIONS
        )

    if coordinator.data.get("energy") is not None:
        entities.extend(
            TewkeEnergySensor(coordinator=coordinator, description=description)
            for description in ENERGY_SENSOR_DESCRIPTIONS
        )

    async_add_entities(entities)


class TewkeSensor(TewkeEntity, SensorEntity):
    """A Tewke BME680 / ambient-light sensor entity."""

    entity_description: TewkeSensorEntityDescription

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        description: TewkeSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        # pylint: disable-next=home-assistant-entity-unique-id-redundant-platform
        self._attr_unique_id = f"{hardware_id}_sensor_{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return True if the sensor is available, False otherwise."""
        return super().available and self.coordinator.data.get("sensors") is not None

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the sensor reading."""
        sensors: SensorData | None = self.coordinator.data.get("sensors")
        if sensors is None:
            return None
        return self.entity_description.value_fn(sensors)


@dataclass(frozen=True, kw_only=True)
class TewkeRadarSensorEntityDescription(SensorEntityDescription):
    """Describes a Tewke radar sensor entity."""

    value_fn: Callable[[RadarData], str | int | None]


RADAR_SENSOR_DESCRIPTIONS: tuple[TewkeRadarSensorEntityDescription, ...] = (
    TewkeRadarSensorEntityDescription(
        key="radar_proximity",
        translation_key="radar_proximity",
        device_class=SensorDeviceClass.ENUM,
        options=["none", "near", "far"],
        value_fn=lambda r: r.proximity.value,
    ),
    TewkeRadarSensorEntityDescription(
        key="radar_near_threshold",
        translation_key="radar_near_threshold",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.thresholds.near.value if r.thresholds else None,
    ),
    TewkeRadarSensorEntityDescription(
        key="radar_near_hysteresis",
        translation_key="radar_near_hysteresis",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.thresholds.near.hysteresis if r.thresholds else None,
    ),
    TewkeRadarSensorEntityDescription(
        key="radar_far_threshold",
        translation_key="radar_far_threshold",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.thresholds.far.value if r.thresholds else None,
    ),
    TewkeRadarSensorEntityDescription(
        key="radar_far_hysteresis",
        translation_key="radar_far_hysteresis",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda r: r.thresholds.far.hysteresis if r.thresholds else None,
    ),
)


class TewkeRadarSensor(TewkeEntity, SensorEntity):
    """A Tewke radar proximity sensor entity."""

    entity_description: TewkeRadarSensorEntityDescription

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        description: TewkeRadarSensorEntityDescription,
    ) -> None:
        """Initialise the radar sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        self._attr_unique_id = f"{hardware_id}_{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return True if the sensor is available, False otherwise."""
        return super().available and self.coordinator.data.get("radar") is not None

    @property
    @override
    def native_value(self) -> str | int | None:
        """Return the sensor reading."""
        radar: RadarData | None = self.coordinator.data.get("radar")
        if radar is None:
            return None
        return self.entity_description.value_fn(radar)


@dataclass(frozen=True, kw_only=True)
class TewkeEnergySensorEntityDescription(SensorEntityDescription):
    """Describes a Tewke energy sensor entity."""

    value_fn: Callable[[EnergyData], float | None]


ENERGY_SENSOR_DESCRIPTIONS: tuple[TewkeEnergySensorEntityDescription, ...] = (
    TewkeEnergySensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda e: e.power,
    ),
    TewkeEnergySensorEntityDescription(
        key="actual_power",
        translation_key="actual_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda e: e.actual_power,
    ),
)


class TewkeEnergySensor(TewkeEntity, SensorEntity):
    """A Tewke power consumption sensor entity."""

    entity_description: TewkeEnergySensorEntityDescription

    def __init__(
        self,
        coordinator: TewkeCoordinator,
        description: TewkeEnergySensorEntityDescription,
    ) -> None:
        """Initialise the energy sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        config = coordinator.data["config"]
        assert config is not None
        hardware_id = config.hardware_id
        self._attr_unique_id = f"{hardware_id}_{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return True if the sensor is available, False otherwise."""
        return super().available and self.coordinator.data.get("energy") is not None

    @property
    @override
    def native_value(self) -> float | None:
        """Return the power reading in watts."""
        energy: EnergyData | None = self.coordinator.data.get("energy")
        if energy is None:
            return None
        return self.entity_description.value_fn(energy)
