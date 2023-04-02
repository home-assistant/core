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
from .entity import AnovaDescriptionEntity
from .models import AnovaData

SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="cook_time",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.STATE, translation_key="state"
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.MODE, translation_key="mode"
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="target_temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.COOK_TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="cook_time_remaining",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.HEATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="heater_temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.TRIAC_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="triac_temperature",
    ),
    SensorEntityDescription(
        key=AnovaPrecisionCookerSensor.WATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="water_temperature",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    anova_data: AnovaData = hass.data[DOMAIN][entry.entry_id]
    sensors: list[AnovaSensor] = []
    for coordinator in anova_data.coordinators:
        sensors.extend(
            [
                AnovaSensor(coordinator, description)
                for description in SENSOR_DESCRIPTIONS
            ]
        )
    async_add_entities(sensors)


class AnovaSensor(AnovaDescriptionEntity, SensorEntity):
    """A sensor using anova coordinator."""

    def __init__(
        self, coordinator: AnovaCoordinator, description: SensorEntityDescription
    ) -> None:
        """Set up an Anova Sensor Entity."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data["sensors"][self.entity_description.key]
