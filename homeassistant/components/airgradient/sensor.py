"""Support for AirGradient sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from airgradient.models import Measures

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import AirGradientMeasurementCoordinator
from .entity import AirGradientEntity


@dataclass(frozen=True, kw_only=True)
class AirGradientSensorEntityDescription(SensorEntityDescription):
    """Describes AirGradient sensor entity."""

    value_fn: Callable[[Measures], StateType]


SENSOR_TYPES: tuple[AirGradientSensorEntityDescription, ...] = (
    AirGradientSensorEntityDescription(
        key="pm01",
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm01,
    ),
    AirGradientSensorEntityDescription(
        key="pm02",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm02,
    ),
    AirGradientSensorEntityDescription(
        key="pm10",
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm10,
    ),
    AirGradientSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.ambient_temperature,
    ),
    AirGradientSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.relative_humidity,
    ),
    AirGradientSensorEntityDescription(
        key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.signal_strength,
    ),
    AirGradientSensorEntityDescription(
        key="tvoc",
        translation_key="total_volatile_organic_component_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.total_volatile_organic_component_index,
    ),
    AirGradientSensorEntityDescription(
        key="nitrogen_index",
        translation_key="nitrogen_index",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.nitrogen_index,
    ),
    AirGradientSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.rco2,
    ),
    AirGradientSensorEntityDescription(
        key="pm003",
        translation_key="pm003_count",
        native_unit_of_measurement="particles/dL",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.pm003_count,
    ),
    AirGradientSensorEntityDescription(
        key="nox_raw",
        translation_key="raw_nitrogen",
        native_unit_of_measurement="ticks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.raw_nitrogen,
    ),
    AirGradientSensorEntityDescription(
        key="tvoc_raw",
        translation_key="raw_total_volatile_organic_component",
        native_unit_of_measurement="ticks",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda status: status.raw_total_volatile_organic_component,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up AirGradient sensor entities based on a config entry."""

    coordinator: AirGradientMeasurementCoordinator = hass.data[DOMAIN][entry.entry_id][
        "measurement"
    ]
    listener: Callable[[], None] | None = None
    not_setup: set[AirGradientSensorEntityDescription] = set(SENSOR_TYPES)

    @callback
    def add_entities() -> None:
        """Add new entities based on the latest data."""
        nonlocal not_setup, listener
        sensor_descriptions = not_setup
        not_setup = set()
        sensors = []
        for description in sensor_descriptions:
            if description.value_fn(coordinator.data) is None:
                not_setup.add(description)
            else:
                sensors.append(AirGradientSensor(coordinator, description))

        if sensors:
            async_add_entities(sensors)
        if not_setup:
            if not listener:
                listener = coordinator.async_add_listener(add_entities)
        elif listener:
            listener()

    add_entities()


class AirGradientSensor(AirGradientEntity, SensorEntity):
    """Defines an AirGradient sensor."""

    entity_description: AirGradientSensorEntityDescription
    coordinator: AirGradientMeasurementCoordinator

    def __init__(
        self,
        coordinator: AirGradientMeasurementCoordinator,
        description: AirGradientSensorEntityDescription,
    ) -> None:
        """Initialize airgradient sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
