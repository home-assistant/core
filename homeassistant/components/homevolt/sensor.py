"""Support for Homevolt sensors."""

from __future__ import annotations

from dataclasses import dataclass
import logging

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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, HomevoltConfigEntry
from .coordinator import HomevoltDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class Description:
    """Sensor metadata description."""

    device_class: SensorDeviceClass | None
    state_class: SensorStateClass | None
    native_unit_of_measurement: str | None


SENSOR_META: dict[SensorType, Description] = {
    SensorType.COUNT: Description(None, SensorStateClass.MEASUREMENT, "N"),
    SensorType.CURRENT: Description(
        SensorDeviceClass.CURRENT,
        SensorStateClass.MEASUREMENT,
        UnitOfElectricCurrent.AMPERE,
    ),
    SensorType.ENERGY_INCREASING: Description(
        SensorDeviceClass.ENERGY,
        SensorStateClass.TOTAL_INCREASING,
        UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SensorType.ENERGY_TOTAL: Description(
        SensorDeviceClass.ENERGY, SensorStateClass.TOTAL, UnitOfEnergy.WATT_HOUR
    ),
    SensorType.FREQUENCY: Description(
        SensorDeviceClass.FREQUENCY, SensorStateClass.MEASUREMENT, UnitOfFrequency.HERTZ
    ),
    SensorType.PERCENTAGE: Description(
        SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, PERCENTAGE
    ),
    SensorType.POWER: Description(
        SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, UnitOfPower.WATT
    ),
    SensorType.SCHEDULE_TYPE: Description(None, None, None),
    SensorType.SIGNAL_STRENGTH: Description(
        SensorDeviceClass.SIGNAL_STRENGTH,
        SensorStateClass.MEASUREMENT,
        SIGNAL_STRENGTH_DECIBELS,
    ),
    SensorType.TEMPERATURE: Description(
        SensorDeviceClass.TEMPERATURE,
        SensorStateClass.MEASUREMENT,
        UnitOfTemperature.CELSIUS,
    ),
    SensorType.TEXT: Description(None, None, None),
    SensorType.VOLTAGE: Description(
        SensorDeviceClass.VOLTAGE,
        SensorStateClass.MEASUREMENT,
        UnitOfElectricPotential.VOLT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Homevolt sensor."""
    coordinator = entry.runtime_data
    entities = []
    for sensor_name, sensor in coordinator.data.sensors.items():
        if sensor.type not in SENSOR_META:
            continue
        sensor_meta = SENSOR_META[sensor.type]
        entities.append(
            HomevoltSensor(
                SensorEntityDescription(
                    key=sensor_name,
                    name=sensor_name,
                    device_class=sensor_meta.device_class,
                    state_class=sensor_meta.state_class,
                    native_unit_of_measurement=sensor_meta.native_unit_of_measurement,
                ),
                coordinator,
            )
        )
    async_add_entities(entities)


class HomevoltSensor(CoordinatorEntity[HomevoltDataUpdateCoordinator], SensorEntity):
    """Representation of a Homevolt sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        description: SensorEntityDescription,
        coordinator: HomevoltDataUpdateCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        device_id = coordinator.data.device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        sensor = coordinator.data.sensors[description.key]
        sensor_device_id = sensor.device_identifier
        device_metadata = coordinator.data.device_metadata.get(sensor_device_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{device_id}_{sensor_device_id}")},
            configuration_url=coordinator.client.hostname,
            manufacturer=MANUFACTURER,
            model=device_metadata.model,
            name=device_metadata.name,
        )

    @property
    def native_value(self) -> StateType:
        """Return the native value of the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key].value
