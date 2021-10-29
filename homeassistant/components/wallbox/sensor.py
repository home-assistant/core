"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.exceptions import IntegrationError
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

    filtered_data = {
        k: coordinator.data[k] for k in SENSOR_TYPES if k in coordinator.data
    }

    async_add_entities(
        [
            WallboxSensor(coordinator, config, description)
            for ent in filtered_data
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
        if (sensor_round := self.entity_description.precision) is not None:
            try:
                return round(
                    self.coordinator.data[self.entity_description.key], sensor_round
                )
            except TypeError as ex:
                raise IntegrationError from ex
        return self.coordinator.data[self.entity_description.key]
