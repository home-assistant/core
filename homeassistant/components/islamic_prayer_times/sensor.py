"""Platform to retrieve Islamic prayer times information for Home Assistant."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IslamicPrayerDataUpdateCoordinator
from .const import DOMAIN, PRAYER_TIMES_ICON, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Islamic prayer times sensor platform."""

    coordinator = hass.data[DOMAIN]

    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(IslamicPrayerTimeSensor(sensor_type, coordinator))

    async_add_entities(entities)


class IslamicPrayerTimeSensor(
    CoordinatorEntity[IslamicPrayerDataUpdateCoordinator], SensorEntity
):
    """Representation of an Islamic prayer time sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = PRAYER_TIMES_ICON
    _attr_should_poll = False

    def __init__(
        self, sensor_type: str, coordinator: IslamicPrayerDataUpdateCoordinator
    ) -> None:
        """Initialize the Islamic prayer time sensor."""
        self.sensor_type = sensor_type
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_type} {SENSOR_TYPES[self.sensor_type]}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return self.sensor_type

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.sensor_type]
