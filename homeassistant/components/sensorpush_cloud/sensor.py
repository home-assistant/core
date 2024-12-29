"""Support for SensorPush Cloud sensors."""

from __future__ import annotations

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_ALTITUDE,
    ATTR_ATMOSPHERIC_PRESSURE,
    ATTR_BATTERY_VOLTAGE,
    ATTR_DEWPOINT,
    ATTR_HUMIDITY,
    ATTR_LAST_UPDATE,
    ATTR_SIGNAL_STRENGTH,
    ATTR_VAPOR_PRESSURE,
    DOMAIN,
    LOGGER,
    MAX_TIME_BETWEEN_UPDATES,
)
from .coordinator import SensorPushCloudConfigEntry, SensorPushCloudCoordinator

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

SENSORS: tuple[SensorEntityDescription, ...] = (
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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SensorPush Cloud sensors."""
    coordinator: SensorPushCloudCoordinator = entry.runtime_data
    device_ids = await coordinator.async_get_device_ids()
    async_add_entities(
        SensorPushCloudSensor(coordinator, entity_description, device_id)
        for entity_description in SENSORS
        for device_id in device_ids
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

        if device_id not in self.coordinator.data:
            LOGGER.warning("Ignoring inactive device: %s", device_id)
            self._attr_available = False
            return

        device = self.coordinator.data[device_id]
        self._attr_unique_id = f"{device.device_id}_{entity_description.key}"
        self._attr_device_info = device.device_info(DOMAIN)

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        if self.device_id not in self.coordinator.data:
            return False  # inactive device
        last_update = self.coordinator.data[self.device_id][ATTR_LAST_UPDATE]
        return bool(dt_util.utcnow() < (last_update + MAX_TIME_BETWEEN_UPDATES))

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        value: StateType = self.coordinator.data[self.device_id][
            self.entity_description.key
        ]
        return value
