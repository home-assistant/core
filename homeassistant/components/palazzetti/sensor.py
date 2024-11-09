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
class PalazzettiSensorEntityDescription(SensorEntityDescription):
    """Describes Palazzetti sensor entity."""


SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="outlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="exhaust_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="pellet_quantity",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
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
    not_setup: set[SensorEntityDescription] = set(SENSOR_DESCRIPTIONS)

    @callback
    def add_entities() -> None:
        """Add new entities based on the latest data."""
        nonlocal not_setup, listener
        sensor_descriptions = not_setup
        not_setup = set()
        sensors = [
            PalazzettiSensor(coordinator, description)
            for description in sensor_descriptions
        ]

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
        """Return the state of the sensor."""
        return getattr(self.coordinator.client, self.entity_description.key)
