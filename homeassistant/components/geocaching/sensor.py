"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from geocachingapi.models import GeocachingStatus

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeocachingDataUpdateCoordinator


@dataclass
class GeocachingRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[GeocachingStatus], str | int | None]


@dataclass
class GeocachingSensorEntityDescription(
    SensorEntityDescription, GeocachingRequiredKeysMixin
):
    """Define Sensor entity description class."""


SENSORS: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="find_count",
        translation_key="find_count",
        icon="mdi:notebook-edit-outline",
        native_unit_of_measurement="caches",
        value_fn=lambda status: status.user.find_count,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        translation_key="hide_count",
        icon="mdi:eye-off-outline",
        native_unit_of_measurement="caches",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.hide_count,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        translation_key="favorite_points",
        icon="mdi:heart-outline",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.favorite_points,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        translation_key="souvenir_count",
        icon="mdi:license",
        native_unit_of_measurement="souvenirs",
        value_fn=lambda status: status.user.souvenir_count,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        translation_key="awarded_favorite_points",
        icon="mdi:heart",
        native_unit_of_measurement="points",
        entity_registry_visible_default=False,
        value_fn=lambda status: status.user.awarded_favorite_points,
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
        self._attr_unique_id = (
            f"{coordinator.data.user.reference_code}_{description.key}"
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
