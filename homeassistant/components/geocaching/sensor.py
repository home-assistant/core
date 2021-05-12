"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, SENSOR_DATA
from .coordinator import GeocachingDataUpdateCoordinator
from .models import GeocachingEntity, GeocachingSensorSettings


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]["COORD"]
    async_add_entities(
        [
            GeocachingSensor(coordinator, key=key, settings=SENSOR_DATA[key])
            for key in SENSOR_DATA
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
            name=f"Geocaching {coordinator.data.user.username} {settings['name']}",
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
