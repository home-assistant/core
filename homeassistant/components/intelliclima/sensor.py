"""Sensor platform for IntelliClima VMC."""

from collections.abc import Callable
from dataclasses import dataclass

from pyintelliclima.intelliclima_types import IntelliClimaECO

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class IntelliClimaSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor entity."""

    value_fn: Callable[[IntelliClimaECO], int | float | str | None]


INTELLICLIMA_SENSORS: tuple[IntelliClimaSensorEntityDescription, ...] = (
    IntelliClimaSensorEntityDescription(
        key="temperature",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda device_data: float(device_data.tamb),
    ),
    IntelliClimaSensorEntityDescription(
        key="humidity",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda device_data: float(device_data.rh),
    ),
    IntelliClimaSensorEntityDescription(
        key="voc",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda device_data: float(device_data.voc_state),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliClima Sensors."""
    coordinator = entry.runtime_data

    entities: list[IntelliClimaSensor] = [
        IntelliClimaSensor(
            coordinator=coordinator, device=ecocomfort2, description=description
        )
        for ecocomfort2 in coordinator.data.ecocomfort2_devices.values()
        for description in INTELLICLIMA_SENSORS
    ]

    async_add_entities(entities)


class IntelliClimaSensor(IntelliClimaECOEntity, SensorEntity):
    """Extends IntelliClimaEntity with Sensor specific logic."""

    entity_description: IntelliClimaSensorEntityDescription

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO,
        description: IntelliClimaSensorEntityDescription,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self.entity_description = description

        self._attr_unique_id = f"{device.id}_{description.key}"

    @property
    def native_value(self) -> int | float | str | None:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self._device_data)
