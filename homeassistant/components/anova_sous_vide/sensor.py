"""Support for Anova Sous Vide Sensors."""
from __future__ import annotations

from anova_wifi import AnovaPrecisionCookerSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ANOVA_CLIENT, ANOVA_FIRMWARE_VERSION, DOMAIN
from .coordinator import AnovaCoordinator

SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    AnovaPrecisionCookerSensor.COOK_TIME: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time",
    ),
    AnovaPrecisionCookerSensor.STATE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.STATE, name="State"
    ),
    AnovaPrecisionCookerSensor.MODE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.MODE, name="Mode"
    ),
    AnovaPrecisionCookerSensor.TARGET_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Target Temperature",
    ),
    AnovaPrecisionCookerSensor.COOK_TIME_REMAINING: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time Remaining",
    ),
    AnovaPrecisionCookerSensor.HEATER_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.HEATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Heater Temperature",
    ),
    AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Triac Temperature",
    ),
    AnovaPrecisionCookerSensor.WATER_TEMPERATURE: SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.WATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Water Temperature",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova Sous Vide device."""
    anova_wifi = hass.data[DOMAIN][entry.entry_id][ANOVA_CLIENT]
    firmware_version = hass.data[DOMAIN][entry.entry_id][ANOVA_FIRMWARE_VERSION]
    coordinator = AnovaCoordinator(hass, anova_wifi, firmware_version)
    await coordinator.async_config_entry_first_refresh()
    sensors = [
        AnovaEntity(coordinator, description, sensor)
        for sensor, description in SENSOR_DESCRIPTIONS.items()
    ]
    async_add_entities(sensors)


class AnovaEntity(CoordinatorEntity[AnovaCoordinator], SensorEntity):
    """An entity using CoordinatorEntity."""

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        description: SensorEntityDescription,
        sensor_update_key: str,
    ) -> None:
        """Set up an Anova Sensor Entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_update_key = sensor_update_key
        self._sensor_data = None
        self._attr_unique_id = (
            f"Anova_{coordinator._device_id}_{description.key}".lower()
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data["sensors"][self._sensor_update_key]
