"""Sensor platform for Huum sauna integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from huum.schemas import HuumStatusResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfRatio, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HuumConfigEntry, HuumDataUpdateCoordinator
from .entity import HuumBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HuumSensorEntityDescription(SensorEntityDescription):
    """Describes a Huum sensor entity."""

    value_fn: Callable[[HuumStatusResponse], int | None]
    exists_fn: Callable[[HuumStatusResponse], bool] = lambda _: True


SENSORS: tuple[HuumSensorEntityDescription, ...] = (
    HuumSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    HuumSensorEntityDescription(
        key="measured_humidity",
        translation_key="measured_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.measured_humidity,
        # Only saunas with a humidity sensor report a measured value.
        exists_fn=lambda data: data.measured_humidity is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HuumConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Huum sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        HuumSensor(coordinator, description)
        for description in SENSORS
        if description.exists_fn(coordinator.data)
    )


class HuumSensor(HuumBaseEntity, SensorEntity):
    """Representation of a Huum sensor."""

    entity_description: HuumSensorEntityDescription

    def __init__(
        self,
        coordinator: HuumDataUpdateCoordinator,
        description: HuumSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> int | None:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)
