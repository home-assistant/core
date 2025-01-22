"""Support for Overseerr sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from python_overseerr import RequestCount

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import REQUESTS
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator
from .entity import OverseerrEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OverseerrSensorEntityDescription(SensorEntityDescription):
    """Describes Overseerr config sensor entity."""

    value_fn: Callable[[RequestCount], int]


SENSORS: tuple[OverseerrSensorEntityDescription, ...] = (
    OverseerrSensorEntityDescription(
        key="total_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.total,
    ),
    OverseerrSensorEntityDescription(
        key="movie_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.movie,
    ),
    OverseerrSensorEntityDescription(
        key="tv_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.tv,
    ),
    OverseerrSensorEntityDescription(
        key="pending_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.pending,
    ),
    OverseerrSensorEntityDescription(
        key="declined_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.declined,
    ),
    OverseerrSensorEntityDescription(
        key="processing_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.processing,
    ),
    OverseerrSensorEntityDescription(
        key="available_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda count: count.available,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverseerrConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Overseerr sensor entities based on a config entry."""

    coordinator = entry.runtime_data
    async_add_entities(
        OverseerrSensor(coordinator, description) for description in SENSORS
    )


class OverseerrSensor(OverseerrEntity, SensorEntity):
    """Defines an Overseerr sensor."""

    entity_description: OverseerrSensorEntityDescription

    def __init__(
        self,
        coordinator: OverseerrCoordinator,
        description: OverseerrSensorEntityDescription,
    ) -> None:
        """Initialize airgradient sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
