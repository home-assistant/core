"""
Support for the Awair indoor air quality monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.awair/
"""

from datetime import datetime, timedelta
import logging
import math

import voluptuous as vol

from homeassistant.const import (
    CONF_ACCESS_TOKEN, CONF_DEVICES, DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['python_awair==0.0.1']

_LOGGER = logging.getLogger(__name__)

ATTR_SCORE = 'score'
ATTR_TIMESTAMP = 'timestamp'
ATTR_COMPONENT = 'component'
ATTR_VALUE = 'value'
ATTR_SENSORS = 'sensors'

CONF_UUID = 'uuid'

DEVICE_CLASS_PM2_5 = 'PM2.5'
DEVICE_CLASS_PM10 = 'PM10'
DEVICE_CLASS_CARBON_DIOXIDE = 'CO2'
DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS = 'VOC'

SENSOR_TYPES = {
    'TEMP': {'device_class': DEVICE_CLASS_TEMPERATURE,
             'unit_of_measurement': TEMP_CELSIUS,
             'icon': 'mdi:thermometer'},
    'HUMID': {'device_class': DEVICE_CLASS_HUMIDITY,
              'unit_of_measurement': '%',
              'icon': 'mdi:water-percent'},
    'CO2': {'device_class': DEVICE_CLASS_CARBON_DIOXIDE,
            'unit_of_measurement': 'ppm',
            'icon': 'mdi:periodic-table-co2'},
    'VOC': {'device_class': DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
            'unit_of_measurement': 'ppb',
            'icon': 'mdi:cloud'},
    # Awair docs don't actually specify the size they measure for 'dust',
    # but 2.5 allows the sensor to show up in HomeKit
    'DUST': {'device_class': DEVICE_CLASS_PM2_5,
             'unit_of_measurement': 'µg/m3',
             'icon': 'mdi:cloud'},
    'PM25': {'device_class': DEVICE_CLASS_PM2_5,
             'unit_of_measurement': 'µg/m3',
             'icon': 'mdi:cloud'},
    'PM10': {'device_class': DEVICE_CLASS_PM10,
             'unit_of_measurement': 'µg/m3',
             'icon': 'mdi:cloud'},
}

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'
AWAIR_QUOTA = 300
THROTTLE = timedelta(minutes=10)

AWAIR_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_UUID): cv.string,
})

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Optional(CONF_DEVICES): [AWAIR_DEVICE_SCHEMA]
})


# Awair *heavily* throttles calls that get user information,
# and calls that get the list of user-owned devices - they
# allow 30 per DAY. So, we permit a user to provide a static
# list of devices, and they may provide the same set of information
# that the devices() call would return. However, the only thing
# used at this time is the `uuid` value.
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Connect to the Awair API and find devices."""
    from python_awair import AwairClient

    token = config.get(CONF_ACCESS_TOKEN)
    client = AwairClient(token, session=async_get_clientsession(hass))

    try:
        all_devices = []
        devices = config.get(CONF_DEVICES, await client.devices())

        # Try to throttle dynamically based on quota and number of devices.
        global THROTTLE
        throttle_minutes = math.ceil(60 / ((AWAIR_QUOTA / len(devices)) / 24))
        THROTTLE = timedelta(minutes=throttle_minutes)

        for device in devices:
            _LOGGER.debug("Found awair device: %s", device)
            awair_data = AwairData(client, device[CONF_UUID])
            await awair_data.async_update()
            for sensor in SENSOR_TYPES:
                if sensor in awair_data.data:
                    awair_sensor = AwairSensor(awair_data, device, sensor)
                    all_devices.append(awair_sensor)

        async_add_entities(all_devices, True)
    except Exception as error:
        _LOGGER.error("Couldn't set up Awair platform: %s", error)


class AwairSensor(Entity):
    """Implementation of an Awair device."""

    def __init__(self, data, device, sensor_type):
        """Initialize the sensor."""
        self._uuid = device[CONF_UUID]
        self._device_class = SENSOR_TYPES[sensor_type]['device_class']
        self._name = 'Awair {}'.format(self._device_class)
        unit = SENSOR_TYPES[sensor_type]['unit_of_measurement']
        self._unit_of_measurement = unit
        self._data = data
        self._type = sensor_type

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self._type]['icon']

    @property
    def state(self):
        """Return the state of the device."""
        return self._data.data[self._type]

    @property
    def score(self):
        """Return the aggregate Awair score."""
        return self._data.data[ATTR_SCORE]

    @property
    def timestamp(self):
        """Return the timestamp of the last sensor reading."""
        return self._data.data[ATTR_TIMESTAMP]

    @property
    def unique_id(self):
        """Return the unique id of this entity."""
        return "{}_{}".format(self._uuid, self._type)

    @property
    def uuid(self):
        """Return the API UUID of this entity."""
        return self._uuid

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data."""
        await self._data.async_update()


class AwairData(Entity):
    """Get data from Awair API."""

    def __init__(self, client, uuid):
        """Initialize the data object."""
        self._client = client
        self._uuid = uuid
        self.data = {}

    @Throttle(THROTTLE)
    async def async_update(self):
        """Get the data from Awair API."""
        resp = await self._client.air_data_latest(self._uuid)
        timestamp = datetime.strptime(resp[0][ATTR_TIMESTAMP], TIME_FORMAT)

        self.data = {ATTR_TIMESTAMP: timestamp,
                     ATTR_SCORE: resp[0][ATTR_SCORE]}

        # The air_data_latest call only returns one item, so this should
        # be safe to only process one entry.
        for sensor in resp[0][ATTR_SENSORS]:
            self.data[sensor[ATTR_COMPONENT]] = sensor[ATTR_VALUE]

        _LOGGER.debug("Got Awair Data for %s: %s", self._uuid, self.data)
        return True
