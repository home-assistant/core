"""Support for Gatus sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from gatus_api import Result

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import GatusConfigEntry, GatusDataUpdateCoordinator
from .entity import GatusEndpointEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GatusSensorEntityDescription(SensorEntityDescription):
    """Class describing Gatus sensor entities."""

    value_fn: Callable[[Result], float | int | str | None]


SENSOR_TYPES: tuple[GatusSensorEntityDescription, ...] = (
    GatusSensorEntityDescription(
        key="response_time",
        translation_key="response_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda result: (
            round(result.duration / 1_000_000, 2)
            if result.duration is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GatusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gatus sensor platform."""
    coordinator = entry.runtime_data

    async_add_entities(
        GatusEndpointSensor(coordinator, entry, endpoint_key, description)
        for endpoint_key in coordinator.data
        for description in SENSOR_TYPES
    )


class GatusEndpointSensor(GatusEndpointEntity, SensorEntity):
    """Representation of a Gatus endpoint sensor."""

    entity_description: GatusSensorEntityDescription

    def __init__(
        self,
        coordinator: GatusDataUpdateCoordinator,
        entry: GatusConfigEntry,
        endpoint_key: str,
        description: GatusSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, endpoint_key)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{endpoint_key}_{description.key}"

    @property
    @override
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        if TYPE_CHECKING:
            assert self.latest_result is not None

        return self.entity_description.value_fn(self.latest_result)
