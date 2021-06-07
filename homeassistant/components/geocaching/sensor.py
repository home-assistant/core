"""Platform for sensor integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_DEFAULT_ENABLED, ATTR_SECTION, DOMAIN, SENSOR_DATA
from .coordinator import GeocachingDataUpdateCoordinator
from .models import GeocachingSensorSettings


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            GeocachingSensor(coordinator, key=key, settings=SENSOR_DATA[key])
            for key in SENSOR_DATA
        ]
    )


class GeocachingSensor(CoordinatorEntity, SensorEntity):
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
        super().__init__(coordinator)
        self.settings = settings
        self.key = key

        self._attr_device_class = settings[ATTR_DEVICE_CLASS]
        self._attr_entity_registry_enabled_default = settings[ATTR_DEFAULT_ENABLED]
        self._attr_icon = settings[ATTR_ICON]
        self._attr_name = (
            f"Geocaching {coordinator.data.user.username} {settings[ATTR_NAME]}"
        )
        self._attr_unique_id = (
            f"geocaching_{coordinator.data.user.reference_code}_{key}"
        )
        self._attr_unit_of_measurement = settings[ATTR_UNIT_OF_MEASUREMENT]

    @property
    def state(self) -> Any:
        """Return the state of the sensor."""
        section = getattr(self.coordinator.data, self.settings[ATTR_SECTION])
        return getattr(section, self.settings[ATTR_STATE])
