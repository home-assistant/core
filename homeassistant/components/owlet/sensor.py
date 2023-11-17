"""Support for Owlet sensors."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN, SLEEP_STATES
from .coordinator import OwletCoordinator
from .entity import OwletBaseEntity


@dataclass
class OwletSensorEntityDescription(SensorEntityDescription):
    """Represent the owlet sensor entity description."""


SENSORS: tuple[OwletSensorEntityDescription, ...] = (
    OwletSensorEntityDescription(
        key="battery_percentage",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OwletSensorEntityDescription(
        key="oxygen_saturation",
        translation_key="o2saturation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:leaf",
    ),
    OwletSensorEntityDescription(
        key="oxygen_10_av",
        translation_key="o2saturation10a",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:leaf",
    ),
    OwletSensorEntityDescription(
        key="heart_rate",
        translation_key="heartrate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:heart-pulse",
    ),
    OwletSensorEntityDescription(
        key="battery_minutes",
        translation_key="batterymin",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OwletSensorEntityDescription(
        key="signal_strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OwletSensorEntityDescription(
        key="skin_temperature",
        translation_key="skintemp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OwletSensorEntityDescription(
        key="sleep_state",
        translation_key="sleepstate",
        device_class=SensorDeviceClass.ENUM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the owlet sensors from config entry."""

    coordinators: list[OwletCoordinator] = list(
        hass.data[DOMAIN][config_entry.entry_id].values()
    )

    sensors = []

    for coordinator in coordinators:
        for sensor in SENSORS:
            if sensor.key in coordinator.sock.properties:
                sensors.append(OwletSensor(coordinator, sensor))

    async_add_entities(sensors)


class OwletSensor(OwletBaseEntity, SensorEntity):
    """Representation of an Owlet sensor."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
        description: OwletSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: OwletSensorEntityDescription = description
        self._attr_unique_id = f"{self.sock.serial}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return sensor value."""

        if (
            self.entity_description.key
            in [
                "heart_rate",
                "battery_minutes",
                "oxygen_saturation",
                "skin_temperature",
                "oxygen_10_av",
                "sleep_state",
            ]
            and self.sock.properties["charging"]
        ):
            return None

        if self.entity_description.key == "sleep_state":
            return SLEEP_STATES[self.sock.properties["sleep_state"]]

        return self.sock.properties[self.entity_description.key]

    @property
    def options(self) -> list[str] | None:
        """Set options for sleep state."""
        if self.entity_description.key != "sleep_state":
            return None
        return list(SLEEP_STATES.values())
