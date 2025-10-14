"""Support for Tilt Hydrometer sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from tiltpi import TiltHydrometerData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import TiltPiConfigEntry, TiltPiDataUpdateCoordinator
from .entity import TiltEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

ATTR_TEMPERATURE = "temperature"
ATTR_GRAVITY = "gravity"


@dataclass(frozen=True, kw_only=True)
class TiltEntityDescription(SensorEntityDescription):
    """Describes TiltHydrometerData sensor entity."""

    value_fn: Callable[[TiltHydrometerData], StateType]


SENSOR_TYPES: Final[list[TiltEntityDescription]] = [
    TiltEntityDescription(
        key=ATTR_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    TiltEntityDescription(
        key=ATTR_GRAVITY,
        translation_key="gravity",
        native_unit_of_measurement="SG",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.gravity,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TiltPiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tilt Hydrometer sensors."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        TiltSensor(
            coordinator,
            description,
            hydrometer,
        )
        for description in SENSOR_TYPES
        for hydrometer in coordinator.data.values()
    )


class TiltSensor(TiltEntity, SensorEntity):
    """Defines a Tilt sensor."""

    entity_description: TiltEntityDescription

    def __init__(
        self,
        coordinator: TiltPiDataUpdateCoordinator,
        description: TiltEntityDescription,
        hydrometer: TiltHydrometerData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, hydrometer)
        self.entity_description = description
        self._attr_unique_id = f"{hydrometer.mac_id}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.current_hydrometer)
