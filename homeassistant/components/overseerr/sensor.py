"""Support for Overseerr sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ISSUES, REQUESTS
from .coordinator import OverseerrConfigEntry, OverseerrCoordinator, OverseerrData
from .entity import OverseerrEntity

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
        value_fn=lambda overseerr_data: overseerr_data["request_count"].total,
    ),
    OverseerrSensorEntityDescription(
        key="movie_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].movie,
    ),
    OverseerrSensorEntityDescription(
        key="tv_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].tv,
    ),
    OverseerrSensorEntityDescription(
        key="pending_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].pending,
    ),
    OverseerrSensorEntityDescription(
        key="declined_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].declined,
    ),
    OverseerrSensorEntityDescription(
        key="processing_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].processing,
    ),
    OverseerrSensorEntityDescription(
        key="available_requests",
        native_unit_of_measurement=REQUESTS,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["request_count"].available,
    ),
    OverseerrSensorEntityDescription(
        key="total_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].total,
    ),
    OverseerrSensorEntityDescription(
        key="video_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].video,
    ),
    OverseerrSensorEntityDescription(
        key="audio_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].audio,
    ),
    OverseerrSensorEntityDescription(
        key="subtitle_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].subtitles,
    ),
    OverseerrSensorEntityDescription(
        key="other_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].others,
    ),
    OverseerrSensorEntityDescription(
        key="open_issues",
        native_unit_of_measurement=ISSUES,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda overseerr_data: overseerr_data["issue_count"].open,
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
