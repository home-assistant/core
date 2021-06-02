"""Platform to retrieve Islamic prayer times information for Home Assistant."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from . import IslamicPrayerDataCoordinator
from .const import DOMAIN, PRAYER_TIMES_ICON, SENSOR_TYPES


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the Islamic prayer times sensor platform."""

    coordinator = hass.data[DOMAIN]

    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(IslamicPrayerTimeSensor(coordinator, sensor_type))

    async_add_entities(entities)


class IslamicPrayerTimeSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Islamic prayer time sensor."""

    _attr_device_class = DEVICE_CLASS_TIMESTAMP
    _attr_icon = PRAYER_TIMES_ICON
    _attr_should_poll = False

    def __init__(self, coordinator: IslamicPrayerDataCoordinator, sensor_type) -> None:
        """Initialize the Islamic prayer time sensor."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.sensor_type = sensor_type

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self.sensor_type} {SENSOR_TYPES[self.sensor_type]}"

    @property
    def unique_id(self) -> str:
        """Return the unique id of the entity."""
        return self.sensor_type

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        return (
            self.coordinator.data.get(self.sensor_type)
            .astimezone(dt_util.UTC)
            .isoformat()
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this 17Track instance."""
        return {
            "identifiers": {(DOMAIN, "Islamic Prayer Times")},
            "name": "Islamic Prayer Times",
            "entry_type": "service",
        }

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )
