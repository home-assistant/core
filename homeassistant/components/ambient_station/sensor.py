"""
Support for Ambient Weather Station Service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ambient_station/
"""
import logging

from homeassistant.components.ambient_station import SENSOR_TYPES
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_NAME
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import ATTR_LAST_DATA, DATA_CLIENT, DOMAIN, TOPIC_UPDATE

DEPENDENCIES = ['ambient_station']
_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up an Ambient PWS sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up an Ambient PWS sensor based on a config entry."""
    ambient = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    sensor_list = []
    for mac_address, station in ambient.stations.items():
        for condition in ambient.monitored_conditions:
            name, unit = SENSOR_TYPES[condition]
            sensor_list.append(
                AmbientWeatherSensor(
                    ambient, mac_address, station[ATTR_NAME], condition, name,
                    unit))

    async_add_entities(sensor_list, True)


class AmbientWeatherSensor(Entity):
    """Define an Ambient sensor."""

    def __init__(
            self, ambient, mac_address, station_name, sensor_type, sensor_name,
            unit):
        """Initialize the sensor."""
        self._ambient = ambient
        self._async_unsub_dispatcher_connect = None
        self._mac_address = mac_address
        self._sensor_name = sensor_name
        self._sensor_type = sensor_type
        self._state = None
        self._station_name = station_name
        self._unit = unit

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{0}_{1}'.format(self._station_name, self._sensor_name)

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def unique_id(self):
        """Return a unique, unchanging string that represents this sensor."""
        return '{0}_{1}'.format(self._mac_address, self._sensor_name)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self):
        """Fetch new state data for the sensor."""
        self._state = self._ambient.stations[
            self._mac_address][ATTR_LAST_DATA].get(self._sensor_type)
