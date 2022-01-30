"""Platform for sensor integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GeocachingDataUpdateCoordinator


@dataclass
class GeocachingRequiredKeysMixin:
    """Mixin for required keys."""

    default_enabled: bool
    section: str
    measurement: str


@dataclass
class GeocachingSensorEntityDescription(
    SensorEntityDescription, GeocachingRequiredKeysMixin
):
    """Define Sensor entity description class."""


SENSOR_DATA: tuple[GeocachingSensorEntityDescription, ...] = (
    GeocachingSensorEntityDescription(
        key="username",
        name="username",
        section="user",
        measurement="username",
        icon="mdi:account",
        default_enabled=False,
    ),
    GeocachingSensorEntityDescription(
        key="find_count",
        name="Total finds",
        section="user",
        measurement="find_count",
        icon="mdi:notebook-edit-outline",
        native_unit_of_measurement="caches",
        default_enabled=True,
    ),
    GeocachingSensorEntityDescription(
        key="hide_count",
        name="Total hides",
        section="user",
        measurement="hide_count",
        icon="mdi:eye-off-outline",
        native_unit_of_measurement="caches",
        default_enabled=True,
    ),
    GeocachingSensorEntityDescription(
        key="favorite_points",
        name="Favorite points",
        section="user",
        measurement="favorite_points",
        icon="mdi:heart-outline",
        native_unit_of_measurement="points",
        default_enabled=True,
    ),
    GeocachingSensorEntityDescription(
        key="souvenir_count",
        name="Total souvenirs",
        section="user",
        measurement="souvenir_count",
        icon="mdi:license",
        native_unit_of_measurement="souvenirs",
        default_enabled=True,
    ),
    GeocachingSensorEntityDescription(
        key="awarded_favorite_points",
        name="Awarded favorite points",
        section="user",
        measurement="awarded_favorite_points",
        icon="mdi:heart",
        native_unit_of_measurement="points",
        default_enabled=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [GeocachingSensor(coordinator, entity_description=item) for item in SENSOR_DATA]
    )


class GeocachingSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: GeocachingSensorEntityDescription
    key: str

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        *,
        entity_description: GeocachingSensorEntityDescription,
    ) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self.key = entity_description.key

        self._attr_entity_registry_enabled_default = (
            entity_description.default_enabled or True
        )
        self._attr_name = (
            f"Geocaching {coordinator.data.user.username} {entity_description.name}"
        )
        self._attr_unique_id = f"geocaching_{coordinator.data.user.reference_code}_{entity_description.key}"

    @property
    def native_value(self) -> Any | None:
        """Return the state of the sensor."""
        section = getattr(self.coordinator.data, self.entity_description.section)
        return getattr(section, self.entity_description.measurement)
