"""Platform to retrieve Islamic prayer times information for Home Assistant."""
import logging

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_TIMESTAMP,
    DATA_UPDATED,
    DOMAIN,
    PRAYER_TIMES_ICON,
    SENSOR_SUFFIX,
    SENSOR_TYPES,
    TIME_STR_FORMAT,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Islamic prayer times sensor platform."""

    client = hass.data[DOMAIN]

    entities = []
    for sensor_type in SENSOR_TYPES:
        entities.append(IslamicPrayerTimeSensor(sensor_type, client))

    async_add_entities(entities, True)


class IslamicPrayerTimeSensor(Entity):
    """Representation of an Islamic prayer time sensor."""

    def __init__(self, sensor_type, client):
        """Initialize the Islamic prayer time sensor."""
        self.sensor_type = sensor_type
        self.client = client
        self._state = self.client.prayer_times_info.get(self.sensor_type)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.sensor_type} {SENSOR_SUFFIX}"

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return f"{DOMAIN}_{self.sensor_type}"

    @property
    def icon(self):
        """Icon to display in the front end."""
        return PRAYER_TIMES_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state.time().strftime(TIME_STR_FORMAT) if self._state else None

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def state_attributes(self):
        """Return datetime as attribute."""
        if self._state:
            return {ATTR_TIMESTAMP: self._state}
        return None

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.async_on_remove(
            async_dispatcher_connect(self.hass, DATA_UPDATED, self.async_write_ha_state)
        )
