"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.geocaching.coordinator import (
    GeocachingDataUpdateCoordinator,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ICON
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from .const import (
    ATTR_DEFAULT_ENABLED,
    ATTR_DEVICE_CLASS,
    ATTR_NAME,
    ATTR_SECTION,
    ATTR_STATE,
    ATTR_UNIT_OF_MEASUREMENT,
    DOMAIN,
    SENSOR_ENTITIES,
)
from .models import GeocachingEntity


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Geocaching sensor entry."""

    coordinator = hass.data[DOMAIN][entry.entry_id]["COORD"]
    async_add_entities(
        [GeocachingSensor(coordinator, key=key) for key in SENSOR_ENTITIES], True
    )


class GeocachingSensor(GeocachingEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(
        self, coordinator: GeocachingDataUpdateCoordinator, *, key: str
    ) -> None:
        """Initialize the Geocaching sensor."""
        self.key = key

        super().__init__(
            coordinator,
            enabled_default=bool(SENSOR_ENTITIES[key][ATTR_DEFAULT_ENABLED]),
            icon=str(SENSOR_ENTITIES[key][ATTR_ICON]),
            name=f"Geocaching {coordinator.data.user.reference_code} {SENSOR_ENTITIES[key][ATTR_NAME]}",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"geocaching_{self.coordinator.data.user.reference_code}_{self.key}"

    @property
    def state(self):
        """Return the state of the sensor."""
        section = getattr(
            self.coordinator.data, SENSOR_ENTITIES[self.key][ATTR_SECTION]
        )
        return getattr(section, SENSOR_ENTITIES[self.key][ATTR_STATE])

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_ENTITIES[self.key][ATTR_UNIT_OF_MEASUREMENT]

    @property
    def device_class(self) -> str | None:
        """Return the device class."""
        return str(SENSOR_ENTITIES[self.key][ATTR_DEVICE_CLASS])
