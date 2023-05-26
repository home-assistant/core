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
class OwletSensorEntityDescriptionMixin:
    """Owlet sensor description mix in."""

    element: str


@dataclass
class OwletSensorEntityDescription(
    SensorEntityDescription, OwletSensorEntityDescriptionMixin
):
    """Represent the owlet sensor entity description."""


SENSORS: tuple[OwletSensorEntityDescription, ...] = (
    OwletSensorEntityDescription(
        key="batterypercentage",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        element="battery_percentage",
    ),
    OwletSensorEntityDescription(
        key="oxygensaturation",
        name="O2 Saturation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        element="oxygen_saturation",
        icon="mdi:leaf",
    ),
    OwletSensorEntityDescription(
        key="oxygensaturation10a",
        name="O2 Saturation 10 Minute Average",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        element="oxygen_10_av",
        icon="mdi:leaf",
    ),
    OwletSensorEntityDescription(
        key="heartrate",
        name="Heart rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        element="heart_rate",
        icon="mdi:heart-pulse",
    ),
    OwletSensorEntityDescription(
        key="batteryminutes",
        name="Battery Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        element="battery_minutes",
    ),
    OwletSensorEntityDescription(
        key="signalstrength",
        name="Signal Strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        element="signal_strength",
    ),
    OwletSensorEntityDescription(
        key="skintemp",
        name="Skin Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        element="skin_temperature",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the owlet sensors from config entry."""

    coordinator: OwletCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[OwletSensor | OwletSleepStateSensor] = [
        OwletSensor(coordinator, sensor) for sensor in SENSORS
    ]
    entities.append(OwletSleepStateSensor(coordinator))

    async_add_entities(entities)


class OwletSensor(OwletBaseEntity, SensorEntity):
    """Representation of an Owlet sensor."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
        sensor_description: OwletSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description: OwletSensorEntityDescription = sensor_description
        self._attr_unique_id = f"{self.sock.serial}-{self.entity_description.name}"

    @property
    def native_value(self) -> StateType:
        """Return sensor value."""

        if (
            self.entity_description.element
            in [
                "heart_rate",
                "battery_minutes",
                "oxygen_saturation",
                "skin_temperature",
                "oxygen_10_av",
            ]
            and self.sock.properties["charging"]
        ):
            return None

        properties = self.sock.properties

        return properties[self.entity_description.element]


class OwletSleepStateSensor(OwletBaseEntity, SensorEntity):
    """Representation of an Owlet sleep state sensor."""

    def __init__(
        self,
        coordinator: OwletCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self.sock.serial}-Sleep State"
        self._attr_icon = "mdi:sleep"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_translation_key = "sleepstate"
        self._attr_name = "Sleep State"

    @property
    def native_value(self) -> str:
        """Return sensor value."""
        if self.sock.properties["charging"]:
            return "Unknown"

        return SLEEP_STATES[self.sock.properties["sleep_state"]]

    @property
    def options(self) -> list[str]:
        """Set options for sleep state."""
        return list(SLEEP_STATES.values())
