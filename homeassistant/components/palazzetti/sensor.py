"""Support for Palazzetti sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfMass, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PalazzettiConfigEntry
from .coordinator import PalazzettiDataUpdateCoordinator
from .entity import PalazzettiEntity


@dataclass(frozen=True, kw_only=True)
class CallableSensorEntityDescription(SensorEntityDescription):
    """Describes a Palazzetti sensor entity that is read from a `Callable`."""

    value_callable: Callable[[], int | float | str]
    """The function that returns the state value for this sensor"""


@dataclass(frozen=True, kw_only=True)
class PropertySensorEntityDescription(SensorEntityDescription):
    """Describes a Palazzetti sensor entity that is read from a `PalazzettiClient` property."""

    presence_flag: None | str
    """`None` if the sensor is always present, name of a `bool` property of the PalazzettiClient otherwise"""


PROPERTY_SENSOR_DESCRIPTIONS: list[PropertySensorEntityDescription] = [
    PropertySensorEntityDescription(
        key="pellet_quantity",
        presence_flag=None,
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="pellet_quantity",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PalazzettiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Palazzetti sensor entities based on a config entry."""

    coordinator = entry.runtime_data

    sensors = [
        PalazzettiSensor(
            coordinator,
            CallableSensorEntityDescription(
                key=sensor.description_key.value,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                state_class=SensorStateClass.MEASUREMENT,
                translation_key=sensor.description_key.value,
                value_callable=sensor.value,
            ),
        )
        for sensor in coordinator.client.list_temperatures()
    ]

    sensors.extend(
        [
            PalazzettiSensor(coordinator, description)
            for description in PROPERTY_SENSOR_DESCRIPTIONS
            if not description.presence_flag
            or getattr(coordinator.client, description.presence_flag)
        ]
    )

    if sensors:
        async_add_entities(sensors)


class PalazzettiSensor(PalazzettiEntity, SensorEntity):
    """Define a Palazzetti sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Palazzetti sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state value of the sensor."""
        if isinstance(self.entity_description, CallableSensorEntityDescription):
            return self.entity_description.value_callable()

        return getattr(self.coordinator.client, self.entity_description.key)
