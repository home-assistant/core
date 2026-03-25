"""Support for Overseerr sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REQUESTS
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator
from .entity import OverseerrEntity
from .models import OverseerrData

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OverseerrSensorEntityDescription(SensorEntityDescription):
    """Describes Overseerr config sensor entity."""

    value_fn: Callable[[OverseerrData], int]


SENSORS: tuple[OverseerrSensorEntityDescription, ...] = (
    OverseerrSensorEntityDescription(
        key="total_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.total,
    ),
    OverseerrSensorEntityDescription(
        key="movie_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.movie,
    ),
    OverseerrSensorEntityDescription(
        key="tv_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.tv,
    ),
    OverseerrSensorEntityDescription(
        key="pending_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.pending,
    ),
    OverseerrSensorEntityDescription(
        key="declined_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.declined,
    ),
    OverseerrSensorEntityDescription(
        key="processing_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.processing,
    ),
    OverseerrSensorEntityDescription(
        key="available_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.requests.available,
    ),
    OverseerrSensorEntityDescription(
        key="total_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.total,
    ),
    OverseerrSensorEntityDescription(
        key="open_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.open,
    ),
    OverseerrSensorEntityDescription(
        key="closed_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.closed,
    ),
    OverseerrSensorEntityDescription(
        key="video_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.video,
    ),
    OverseerrSensorEntityDescription(
        key="audio_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.audio,
    ),
    OverseerrSensorEntityDescription(
        key="subtitle_issues",
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.issues.subtitles,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverseerrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
        """Initialize Overseerr sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.key

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
