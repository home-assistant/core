"""Support for Anova Sensors."""

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

from .const import DOMAIN
from .coordinator import AnovaCoordinator
from .entity import AnovaEntity

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time",
    ),
    SensorEntityDescription(key=AnovaPrecisionCookerSensor.STATE, name="State"),
    SensorEntityDescription(key=AnovaPrecisionCookerSensor.MODE, name="Mode"),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Target Temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        name="Cook Time Remaining",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.HEATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Heater Temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Triac Temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.WATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        name="Water Temperature",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
        sensors = [
            AnovaSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS
        ]
        async_add_entities(sensors)


class AnovaSensor(AnovaEntity, SensorEntity):
    """A sensor using anova coordinator."""

    def __init__(
        self, coordinator: AnovaCoordinator, description: SensorEntityDescription
    ) -> None:
        """Set up an Anova Sensor Entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_update_key = description.key
        self._sensor_data = None
        self._attr_unique_id = (
            f"{coordinator.device_unique_id}_{description.key}".lower()
        )
        self._attr_device_info = coordinator.device_info
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data["sensors"][self._sensor_update_key]
