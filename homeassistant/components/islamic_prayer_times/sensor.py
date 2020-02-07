"""Platform to retrieve Islamic prayer times information for Home Assistant."""
import logging

from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DATA_UPDATED, DOMAIN, PRAYER_TIMES_ICON, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


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
        self.unsub_update = None

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

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        self.unsub_update = async_dispatcher_connect(
            self.hass, DATA_UPDATED, self._schedule_immediate_update
        )

    @callback
    def _schedule_immediate_update(self):
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Update the sensor."""
        if self.client.prayer_times_info is not None:
            prayer_time = self.client.prayer_times_info[self.name]
            pt_dt = self.client.get_prayer_time_as_dt(prayer_time)
            self._state = pt_dt.isoformat()

    async def will_remove_from_hass(self):
        """Unsubscribe from update dispatcher."""
        if self.unsub_update:
            self.unsub_update()
            self.unsub_update = None
