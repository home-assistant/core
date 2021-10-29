"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CONNECTIONS,
    DOMAIN,
    SENSOR_TYPES,
    WallboxSensorEntityDescription,
)

CONF_STATION = "station"
UPDATE_INTERVAL = 30


async def async_setup_entry(hass, config, async_add_entities):
    """Create wallbox sensor entities in HASS."""
    coordinator = hass.data[DOMAIN][CONF_CONNECTIONS][config.entry_id]

    async_add_entities(
        [
            WallboxSensor(coordinator, config, description)
            for ent in coordinator.data
            if (description := SENSOR_TYPES[ent])
        ]
    )


class WallboxSensor(CoordinatorEntity, SensorEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSensorEntityDescription

    def __init__(
        self, coordinator, config, description: WallboxSensorEntityDescription
    ):
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{config.title} {description.name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]
