"""Platform to retrieve Islamic prayer times information for Home Assistant."""
import logging

from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.helpers.entity import Entity
from .const import (
    DOMAIN,
    PRAYER_TIMES_ICON,
    SENSOR_TYPES,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import config from configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Islamic prayer times sensor platform."""

    client = hass.data[DOMAIN]

    dev = []
    for sensor_type in SENSOR_TYPES:
        dev.append(IslamicPrayerTimeSensor(sensor_type, client))

    async_add_entities(dev, True)


class IslamicPrayerTimeSensor(Entity):
    """Representation of an Islamic prayer time sensor."""

    ENTITY_ID_FORMAT = "sensor.islamic_prayer_time_{}"

    def __init__(self, sensor_type, client):
        """Initialize the Islamic prayer time sensor."""
        self.sensor_type = sensor_type
        self.entity_id = self.ENTITY_ID_FORMAT.format(self.sensor_type)
        self.client = client
        self._name = self.sensor_type.capitalize()
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return self.entity_id

    @property
    def icon(self):
        """Icon to display in the front end."""
        return PRAYER_TIMES_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.client.available

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TIMESTAMP

    async def async_update(self):
        """Update the sensor."""
        prayer_time = self.client.prayer_times_info[self.name]
        pt_dt = self.client.get_prayer_time_as_dt(prayer_time)
        self._state = pt_dt.isoformat()
