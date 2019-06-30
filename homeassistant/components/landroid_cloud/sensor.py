"""Support for monitoring Worx Landroid Sensors."""
from datetime import datetime, timedelta
import logging
import time

from homeassistant.components import sensor
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import API_WORX_SENSORS, LANDROID_API, UPDATE_SIGNAL

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the available sensors for Worx Landroid."""
    if discovery_info is None:
        return

    entities = []
    api = hass.data[LANDROID_API]

    info = discovery_info[0]
    for sensor in API_WORX_SENSORS:
        name = '{}_{}'.format(info['name'].lower(), sensor.lower())
        friendly_name = '{} {}'.format(info['friendly'], sensor)
        sensor_type = sensor
        _LOGGER.debug("Init Landroid %s sensor", sensor_type)
        entity = LandroidSensor(api, name, sensor_type, friendly_name)
        entities.append(entity)

    async_add_entities(entities, True)


class LandroidSensor(Entity):
    """Class to create and populate a Landroid Sensor."""

    def __init__(self, api, name, sensor_type, friendly_name):
        """Init new sensor."""

        self._api = api
        self._attributes = {}
        self._available = False
        self._name = friendly_name
        self._state = None
        self._sensor_type = sensor_type
        self.entity_id = sensor.ENTITY_ID_FORMAT.format(name)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return sensor attributes."""
        return self._attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return API_WORX_SENSORS[self._sensor_type]['unit']

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return API_WORX_SENSORS[self._sensor_type]['icon']

    @property
    def should_poll(self):
        """Return False as entity is updated from the component."""
        return False

    @property
    def state(self):
        """Return sensor state."""
        return self._state

    @callback
    def update_callback(self):
        """Get new data and update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Connect update callbacks."""
        async_dispatcher_connect(
            self.hass, UPDATE_SIGNAL, self.update_callback)

    def _get_data(self):
        """Return new data from the api cache."""
        data = self._api.get_data(self._sensor_type)
        self._available = True
        return data

    def update(self):
        """Update the sensor."""
        data = self._get_data()
        state = data.pop('state')
        _LOGGER.debug("Mower %s State %s", self._name, state)
        self._attributes.update(data)
        self._state = state