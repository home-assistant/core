"""Support for Homevolt sensors."""

from __future__ import annotations

from homevolt.models import SensorType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator
from .entity import HomevoltEntity

PARALLEL_UPDATES = 0  # Coordinator-based updates

SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SensorType.COUNT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key=SensorType.ENERGY_TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key=SensorType.ENERGY_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    SensorEntityDescription(
        key=SensorType.FREQUENCY,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    SensorEntityDescription(
        key=SensorType.PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key=SensorType.POWER,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key=SensorType.SCHEDULE_TYPE,
    ),
    SensorEntityDescription(
        key=SensorType.SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
    ),
    SensorEntityDescription(
        key=SensorType.TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key=SensorType.TEXT,
    ),
    SensorEntityDescription(
        key=SensorType.VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SensorEntityDescription(
        key=SensorType.CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homevolt sensor."""
    coordinator = entry.runtime_data
    entities = []
    sensors_by_key = {sensor.key: sensor for sensor in SENSORS}
    for sensor_key, sensor in coordinator.data.sensors.items():
        if (description := sensors_by_key.get(sensor.type)) is None:
            continue
        entities.append(
            HomevoltSensor(
                description,
                coordinator,
                sensor_key,
            )
        )
    async_add_entities(entities)


class HomevoltSensor(HomevoltEntity, SensorEntity):
    """Representation of a Homevolt sensor."""

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: HomevoltDataUpdateCoordinator,
        sensor_key: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        device_id = coordinator.data.device_id
        self._attr_unique_id = f"{device_id}_{sensor_key}"
        sensor_data = coordinator.data.sensors[sensor_key]
        self._attr_translation_key = sensor_data.slug
        self._sensor_key = sensor_key
        super().__init__(coordinator, sensor_data.device_identifier)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._sensor_key in self.coordinator.data.sensors

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.coordinator.data.sensors[self._sensor_key].value
