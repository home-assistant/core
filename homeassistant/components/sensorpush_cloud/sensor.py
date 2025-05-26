"""Support for SensorPush Cloud sensors."""

from __future__ import annotations

from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfPressure,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MAX_TIME_BETWEEN_UPDATES
from .coordinator import SensorPushCloudConfigEntry, SensorPushCloudCoordinator

ATTR_ALTITUDE: Final = "altitude"
ATTR_ATMOSPHERIC_PRESSURE: Final = "atmospheric_pressure"
ATTR_BATTERY_VOLTAGE: Final = "battery_voltage"
ATTR_DEWPOINT: Final = "dewpoint"
ATTR_HUMIDITY: Final = "humidity"
ATTR_SIGNAL_STRENGTH: Final = "signal_strength"
ATTR_VAPOR_PRESSURE: Final = "vapor_pressure"

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SENSORS: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        key=ATTR_ALTITUDE,
        device_class=SensorDeviceClass.DISTANCE,
        entity_registry_enabled_default=False,
        translation_key="altitude",
        native_unit_of_measurement=UnitOfLength.FEET,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_ATMOSPHERIC_PRESSURE,
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfPressure.INHG,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        translation_key="battery_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_DEWPOINT,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        translation_key="dewpoint",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_SIGNAL_STRENGTH,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=ATTR_VAPOR_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        entity_registry_enabled_default=False,
        translation_key="vapor_pressure",
        native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SensorPushCloudConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SensorPush Cloud sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        SensorPushCloudSensor(coordinator, entity_description, device_id)
        for entity_description in SENSORS
        for device_id in coordinator.data
    )


class SensorPushCloudSensor(
    CoordinatorEntity[SensorPushCloudCoordinator], SensorEntity
):
    """SensorPush Cloud sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SensorPushCloudCoordinator,
        entity_description: SensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.device_id = device_id

        device = coordinator.data[device_id]
        self._attr_unique_id = f"{device.device_id}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            manufacturer=device.manufacturer,
            model=device.model,
            name=device.name,
        )

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if self.device_id in self.coordinator.data:
            last_update = self.coordinator.data[self.device_id].last_update
            if dt_util.utcnow() >= (last_update + MAX_TIME_BETWEEN_UPDATES):
                return False
        return super().available

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self.device_id][self.entity_description.key]
