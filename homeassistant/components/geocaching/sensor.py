"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.geocaching.coordinator import (
    GeocachingDataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN
from .models import GeocachingEntity, GeocachingSensorSettings


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""

    sensor_data = {
        "username": GeocachingSensorSettings(
            name="Username",
            section="user",
            state="username",
            unit_of_measurement=None,
            device_class=None,
            icon="mdi:account",
            default_enabled=True,
        ),
        "find_count": GeocachingSensorSettings(
            name="Total finds",
            section="user",
            state="find_count",
            unit_of_measurement="caches",
            device_class=None,
            icon="mdi:notebook-edit-outline",
            default_enabled=True,
        ),
        "hide_count": GeocachingSensorSettings(
            name="Total hides",
            section="user",
            state="hide_count",
            unit_of_measurement="caches",
            device_class=None,
            icon="mdi:eye-off-outline",
            default_enabled=True,
        ),
        "favorite_points": GeocachingSensorSettings(
            name="Favorite points",
            section="user",
            state="favorite_points",
            unit_of_measurement="points",
            device_class=None,
            icon="mdi:heart-outline",
            default_enabled=True,
        ),
        "souvenir_count": GeocachingSensorSettings(
            name="Total souvenirs",
            section="user",
            state="souvenir_count",
            unit_of_measurement="souvenirs",
            device_class=None,
            icon="mdi:license",
            default_enabled=True,
        ),
        "awarded_favorite_points": GeocachingSensorSettings(
            name="Awarded favorite points",
            section="user",
            state="awarded_favorite_points",
            unit_of_measurement="points",
            device_class=None,
            icon="mdi:heart",
            default_enabled=True,
        ),
    }

    coordinator = hass.data[DOMAIN][entry.entry_id]["COORD"]
    async_add_entities(
        [
            GeocachingSensor(coordinator, key=key, settings=sensor_data[key])
            for key in sensor_data
        ]
    )


class GeocachingSensor(GeocachingEntity, SensorEntity):
    """Representation of a Sensor."""

    settings: GeocachingSensorSettings
    key: str

    def __init__(
        self,
        coordinator: GeocachingDataUpdateCoordinator,
        *,
        key: str,
        settings: GeocachingSensorSettings,
    ) -> None:
        """Initialize the Geocaching sensor."""

        super().__init__(
            coordinator,
            enabled_default=settings["default_enabled"],
            icon=settings["icon"],
            name=f"Geocaching {coordinator.data.user.reference_code} {settings['name']}",
        )
        self.settings = settings
        self.key = key

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"geocaching_{self.coordinator.data.user.reference_code}_{self.key}"

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        section = getattr(self.coordinator.data, self.settings["section"])
        return getattr(section, self.settings["state"])

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self.settings["unit_of_measurement"]

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        return self.settings["device_class"]
