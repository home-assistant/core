"""The Aprilaire sensor component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from pyaprilaire.const import Attribute

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AprilaireConfigEntry, AprilaireCoordinator
from .entity import BaseAprilaireEntity

DEHUMIDIFICATION_STATUS_MAP: dict[StateType, str] = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "on",
    4: "off",
}

HUMIDIFICATION_STATUS_MAP: dict[StateType, str] = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "off",
}

VENTILATION_STATUS_MAP: dict[StateType, str] = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "idle",
    4: "idle",
    5: "idle",
    6: "off",
}

AIR_CLEANING_STATUS_MAP: dict[StateType, str] = {
    0: "idle",
    1: "idle",
    2: "on",
    3: "off",
}

FAN_STATUS_MAP: dict[StateType, str] = {0: "off", 1: "on"}


def get_entities(
    entity_class: type[BaseAprilaireSensor],
    coordinator: AprilaireCoordinator,
    unique_id: str,
    descriptions: tuple[AprilaireSensorDescription, ...],
) -> list[BaseAprilaireSensor]:
    """Get the entities for a list of sensor descriptions."""

    entities = (
        entity_class(coordinator, description, unique_id)
        for description in descriptions
    )

    return [entity for entity in entities if entity.exists]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AprilaireConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aprilaire sensor devices."""

    coordinator = config_entry.runtime_data

    assert config_entry.unique_id is not None

    entities = (
        get_entities(
            AprilaireHumiditySensor,
            coordinator,
            config_entry.unique_id,
            HUMIDITY_SENSORS,
        )
        + get_entities(
            AprilaireTemperatureSensor,
            coordinator,
            config_entry.unique_id,
            TEMPERATURE_SENSORS,
        )
        + get_entities(
            AprilaireStatusSensor, coordinator, config_entry.unique_id, STATUS_SENSORS
        )
    )

    async_add_entities(entities)


@dataclass(frozen=True, kw_only=True)
class AprilaireSensorDescription(SensorEntityDescription):
    """Class describing Aprilaire sensor entities."""

    status_key: str | None
    value_key: str


@dataclass(frozen=True, kw_only=True)
class AprilaireStatusSensorDescription(AprilaireSensorDescription):
    """Class describing Aprilaire status sensor entities."""

    status_map: dict[StateType, str]


HUMIDITY_SENSORS: tuple[AprilaireSensorDescription, ...] = (
    AprilaireSensorDescription(
        key="indoor_humidity_controlling_sensor",
        translation_key="indoor_humidity_controlling_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        status_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS,
        value_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
    ),
    AprilaireSensorDescription(
        key="outdoor_humidity_controlling_sensor",
        translation_key="outdoor_humidity_controlling_sensor",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        status_key=Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS,
        value_key=Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
    ),
)

TEMPERATURE_SENSORS: tuple[AprilaireSensorDescription, ...] = (
    AprilaireSensorDescription(
        key="indoor_temperature_controlling_sensor",
        translation_key="indoor_temperature_controlling_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        status_key=Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS,
        value_key=Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE,
    ),
    AprilaireSensorDescription(
        key="outdoor_temperature_controlling_sensor",
        translation_key="outdoor_temperature_controlling_sensor",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        status_key=Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS,
        value_key=Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_VALUE,
    ),
)

STATUS_SENSORS: tuple[AprilaireSensorDescription, ...] = (
    AprilaireStatusSensorDescription(
        key="dehumidification_status",
        translation_key="dehumidification_status",
        device_class=SensorDeviceClass.ENUM,
        status_key=Attribute.DEHUMIDIFICATION_AVAILABLE,
        value_key=Attribute.DEHUMIDIFICATION_STATUS,
        status_map=DEHUMIDIFICATION_STATUS_MAP,
        options=list(set(DEHUMIDIFICATION_STATUS_MAP.values())),
    ),
    AprilaireStatusSensorDescription(
        key="humidification_status",
        translation_key="humidification_status",
        device_class=SensorDeviceClass.ENUM,
        status_key=Attribute.HUMIDIFICATION_AVAILABLE,
        value_key=Attribute.HUMIDIFICATION_STATUS,
        status_map=HUMIDIFICATION_STATUS_MAP,
        options=list(set(HUMIDIFICATION_STATUS_MAP.values())),
    ),
    AprilaireStatusSensorDescription(
        key="ventilation_status",
        translation_key="ventilation_status",
        device_class=SensorDeviceClass.ENUM,
        status_key=Attribute.VENTILATION_AVAILABLE,
        value_key=Attribute.VENTILATION_STATUS,
        status_map=VENTILATION_STATUS_MAP,
        options=list(set(VENTILATION_STATUS_MAP.values())),
    ),
    AprilaireStatusSensorDescription(
        key="air_cleaning_status",
        translation_key="air_cleaning_status",
        device_class=SensorDeviceClass.ENUM,
        status_key=Attribute.AIR_CLEANING_AVAILABLE,
        value_key=Attribute.AIR_CLEANING_STATUS,
        status_map=AIR_CLEANING_STATUS_MAP,
        options=list(set(AIR_CLEANING_STATUS_MAP.values())),
    ),
    AprilaireStatusSensorDescription(
        key="fan_status",
        translation_key="fan_status",
        device_class=SensorDeviceClass.ENUM,
        status_key=None,
        value_key=Attribute.FAN_STATUS,
        status_map=FAN_STATUS_MAP,
        options=list(set(FAN_STATUS_MAP.values())),
    ),
)


class BaseAprilaireSensor(BaseAprilaireEntity, SensorEntity):
    """Base sensor entity for Aprilaire."""

    entity_description: AprilaireSensorDescription
    status_sensor_available_value: int | None = None
    status_sensor_exists_values: list[int]

    def __init__(
        self,
        coordinator: AprilaireCoordinator,
        description: AprilaireSensorDescription,
        unique_id: str,
    ) -> None:
        """Initialize a sensor for an Aprilaire device."""

        self.entity_description = description

        super().__init__(coordinator, unique_id)

    @property
    def exists(self) -> bool:
        """Return True if the sensor exists."""

        if self.entity_description.status_key is None:
            return True

        return (
            self.coordinator.data.get(self.entity_description.status_key)
            in self.status_sensor_exists_values
        )

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""

        if (
            self.entity_description.status_key is None
            or self.status_sensor_available_value is None
        ):
            return True

        if not super().available:
            return False

        return (
            self.coordinator.data.get(self.entity_description.status_key)
            == self.status_sensor_available_value
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""

        # Valid cast as pyaprilaire only provides str | int | float
        return cast(
            StateType, self.coordinator.data.get(self.entity_description.value_key)
        )


class AprilaireHumiditySensor(BaseAprilaireSensor):
    """Humidity sensor entity for Aprilaire."""

    status_sensor_available_value = 0
    status_sensor_exists_values = [0, 1, 2]


class AprilaireTemperatureSensor(BaseAprilaireSensor):
    """Temperature sensor entity for Aprilaire."""

    status_sensor_available_value = 0
    status_sensor_exists_values = [0, 1, 2]

    @property
    def suggested_display_precision(self) -> int | None:
        """Return the suggested number of decimal digits for display."""
        if self.unit_of_measurement == UnitOfTemperature.CELSIUS:
            return 1

        return 0


class AprilaireStatusSensor(BaseAprilaireSensor):
    """Status sensor entity for Aprilaire."""

    status_sensor_exists_values = [1, 2]
    entity_description: AprilaireStatusSensorDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor mapped to the status option."""

        raw_value = super().native_value

        return self.entity_description.status_map.get(raw_value)
