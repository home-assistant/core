"""Platform for sensor integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from geocachingapi.models import GeocachingStatus

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, GEOCACHING_ID_SENSOR_FORMAT
from .coordinator import GeocachingDataUpdateCoordinator
from .entities import get_cache_entities


@dataclass(frozen=True, kw_only=True)
class GeocachingSensorEntityDescription(SensorEntityDescription):
    """Define Sensor entity description class."""

    value_fn: Callable[[GeocachingStatus], str | int | None]


SENSORS: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="find_count",
        translation_key="find_count",
        native_unit_of_measurement="caches",
        value_fn=lambda status: status.user.find_count,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        translation_key="hide_count",
        native_unit_of_measurement="caches",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.hide_count,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        translation_key="favorite_points",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        translation_key="souvenir_count",
        native_unit_of_measurement="souvenirs",
        value_fn=lambda status: status.user.souvenir_count,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        translation_key="awarded_favorite_points",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.awarded_favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="nearby_caches",
        translation_key="nearby_caches",
        native_unit_of_measurement="caches",
        value_fn=lambda status: len(status.nearby_caches),
    ),
    GeocachingSensorEntityDescription(
        key="total_tracked_distance_traveled",
        translation_key="total_tracked_distance_traveled",
        native_unit_of_measurement="km",
        value_fn=lambda status: round(
            sum(
                [
                    trackable.kilometers_traveled or 0
                    for trackable in status.trackables.values()
                ]
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        GeocachingSensor(coordinator, description) for description in SENSORS
    )

    # Temporary: Get the nearby caches
    status: GeocachingStatus = await coordinator._async_update_data()  # noqa: SLF001
    entities: list[Entity] = []
    for cache in status.nearby_caches[:3]:
        entities.extend(get_cache_entities(coordinator, cache))
    async_add_entities(entities)


class GeocachingSensor(
    CoordinatorEntity[GeocachingDataUpdateCoordinator], SensorEntity
):
    """Representation of a Sensor."""

    entity_description: GeocachingSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        description: GeocachingSensorEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = GEOCACHING_ID_SENSOR_FORMAT.format(
            coordinator.data.user.reference_code, description.key
        )
        self._attr_device_info = DeviceInfo(
            name=f"Geocaching {coordinator.data.user.username}",
            identifiers={(DOMAIN, cast(str, coordinator.data.user.reference_code))},
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="Groundspeak, Inc.",
        )

    @property
    def native_value(self) -> str | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
