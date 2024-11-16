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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import PalazzettiConfigEntry
from .coordinator import PalazzettiDataUpdateCoordinator


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
    listener: Callable[[], None] | None = None
    not_setup: set[PropertySensorEntityDescription] = set(PROPERTY_SENSOR_DESCRIPTIONS)

    @callback
    def add_entities() -> None:
        """Add new entities based on the latest data."""
        nonlocal not_setup, listener
        sensor_descriptions = not_setup
        not_setup = set()

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
                for description in sensor_descriptions
                if not description.presence_flag
                or getattr(coordinator.client, description.presence_flag)
            ]
        )

        if sensors:
            async_add_entities(sensors)
        if not_setup:
            if not listener:
                listener = coordinator.async_add_listener(add_entities)
        elif listener:
            listener()

    add_entities()


class PalazzettiSensor(SensorEntity):
    """Define a Palazzetti sensor."""

    entity_description: SensorEntityDescription
    coordinator: PalazzettiDataUpdateCoordinator
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: PalazzettiDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize Palazzetti sensor."""
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.client.mac}-{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the state value of the sensor."""
        if isinstance(self.entity_description, CallableSensorEntityDescription):
            return self.entity_description.value_callable()

        return getattr(self.coordinator.client, self.entity_description.key)
