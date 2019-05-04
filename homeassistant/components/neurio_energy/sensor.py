"""Neurio Energy Sensor for Homeassisant."""
import logging
import json
from datetime import timedelta

import requests
import requests.exceptions
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY
from homeassistant.const import POWER_WATT
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_API_SECRET = 'api_secret'
CONF_SENSOR_ID = 'sensor_id'
CONF_SENSOR_IP = 'sensor_ip'

ACTIVE_NAME = 'Energy Usage'
DAILY_NAME = 'Daily Energy Usage'
GENERATION_NAME = 'Solar Generation'
GENERATION_DAILY_NAME = 'Generation Total'
NET_CONSUMPTION = 'Net Consumption'
JSON_DATASET = 'API Data Retrieval'

ACTIVE_TYPE = 'active'
DAILY_TYPE = 'daily'

ICON = 'mdi:flash'

MIN_TIME_BETWEEN_DAILY_UPDATES = timedelta(seconds=30)
MIN_TIME_BETWEEN_ACTIVE_UPDATES = timedelta(seconds=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_API_SECRET): cv.string,
    vol.Optional(CONF_SENSOR_ID): cv.string,
    vol.Optional(CONF_SENSOR_IP): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Neurio sensor."""
    api_key = config.get(CONF_API_KEY)
    api_secret = config.get(CONF_API_SECRET)
    sensor_id = config.get(CONF_SENSOR_ID)
    sensor_ip = config.get(CONF_SENSOR_IP)

    data = NeurioData(api_key, api_secret, sensor_id, sensor_ip)

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_dataset():
        """Update the data set for the other functions."""
        data.get_dataset()

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_daily():
        """Update the daily power usage."""
        data.get_daily_usage()

    @Throttle(MIN_TIME_BETWEEN_ACTIVE_UPDATES)
    def update_active():
        """Update the active power usage."""
        data.get_active_power()

    @Throttle(MIN_TIME_BETWEEN_ACTIVE_UPDATES)
    def update_generation():
        """Update the active power usage."""
        data.get_active_generation()

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_generation_daily():
        """Update the active power usage."""
        data.get_daily_generation()

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_net_consumption():
        """Update the active power usage."""
        data.get_net_consumption()

    update_dataset()
    update_daily()
    update_active()
    update_generation()
    update_generation_daily()
    update_net_consumption()

    # Update Dataset
    add_entities([NeurioEnergy(data,
                               JSON_DATASET,
                               DAILY_TYPE,
                               update_dataset)]
                 )
    # Active power sensor
    add_entities([NeurioEnergy(data,
                               ACTIVE_NAME,
                               ACTIVE_TYPE,
                               update_active)]
                 )
    add_entities([NeurioEnergy(data,
                               GENERATION_NAME,
                               ACTIVE_TYPE,
                               update_generation)]
                 )
    # Daily power sensor
    add_entities([NeurioEnergy(data,
                               DAILY_NAME,
                               DAILY_TYPE,
                               update_daily)]
                 )
    add_entities([NeurioEnergy(data,
                               GENERATION_DAILY_NAME,
                               DAILY_TYPE,
                               update_generation_daily)]
                 )
    add_entities([NeurioEnergy(data,
                               NET_CONSUMPTION,
                               DAILY_TYPE,
                               update_net_consumption)]
                 )


class NeurioData:
    """Stores data retrieved from Neurio sensor."""

    def __init__(self, api_key, api_secret, sensor_id, sensor_ip):
        """Initialize the data."""
        import neurio

        self.api_key = api_key
        self.api_secret = api_secret
        self.sensor_id = sensor_id
        self.sensor_ip = sensor_ip

        self._dataset = None
        self._daily_usage = None
        self._active_power = None
        self._active_generation = None
        self._generation_daily = None
        self._net_consumption = None

        self._state = None

        neurio_tp = neurio.TokenProvider(key=api_key, secret=api_secret)
        self.neurio_client = neurio.Client(token_provider=neurio_tp)

        if not self.sensor_id:
            user_info = self.neurio_client.get_user_information()
            _LOGGER.warning("Sensor ID auto-detected: %s", user_info[
                "locations"][0]["sensors"][0]["sensorId"])
            self.sensor_id = user_info[
                "locations"][0]["sensors"][0]["sensorId"]

    @property
    def dataset(self):
        """Return latest data."""
        return self._dataset

    @property
    def daily_usage(self):
        """Return latest daily usage value."""
        return self._daily_usage

    @property
    def active_power(self):
        """Return latest active power value."""
        return self._active_power

    @property
    def active_generation(self):
        """Return latest active power value."""
        return self._active_generation

    @property
    def daily_generation(self):
        """Return latest active power value."""
        return self._daily_generation

    @property
    def net_consumption(self):
        """Return latest active power value."""
        return self._net_consumption

    def get_dataset(self):
        """Get the most recent data from the api once so we don't hit the ratelimit each hour."""

        start_time = dt_util.start_of_local_day() \
            .astimezone(dt_util.UTC).isoformat()
        end_time = dt_util.utcnow().isoformat()

        _LOGGER.debug('Start: %s, End: %s', start_time, end_time)

        try:
            self._dataset = self.neurio_client \
                .get_samples_stats(self.sensor_id, start_time, 'days', end_time)
        except (requests.exceptions.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update dataset")
            return None

    def get_active_power(self):
        """Return current power value."""
        header = {'Authorization': 'bearer <token>'}
        resp = requests.get('http://'+self.sensor_ip+'/current-sample',
                            headers=header,
                            verify=False
                            )
        try:
            sample = json.loads(resp.text)
            self._active_power = sample['channels'][4]['p_W']
        except (requests.exceptions.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update current power usage")
            return None

    def get_active_generation(self):
        """Return current solar generation value."""
        header = {'Authorization': 'bearer <token>'}
        resp = requests.get('http://'+self.sensor_ip+'/current-sample',
                            headers=header,
                            verify=False
                            )
        try:
            sample = json.loads(resp.text)
            self._active_generation = sample['channels'][3]['p_W']
        except (requests.exceptions.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update current generation")
            return None

    def get_daily_usage(self):
        """Return current daily power usage."""
        kwh = 0

        history = self._dataset
        for result in history:
            kwh += result['consumptionEnergy'] / 3600000
        self._daily_usage = round(kwh, 2)

    def get_daily_generation(self):
        """Return current daily power usage."""
        kwh = 0

        history = self._dataset
        for result in history:
            kwh += result['generationEnergy'] / 3600000
        self._daily_generation = round(kwh, 2)

    def get_net_consumption(self):
        """Return current daily power usage."""
        kwhIn = 0
        kwhOut = 0

        history = self._dataset
        for result in history:
            kwhIn += result['importedEnergy'] / 3600000
        for result in history:
            kwhOut += result['exportedEnergy'] / 3600000
        self._net_consumption = round(kwhIn-kwhOut, 2)


class NeurioEnergy(Entity):
    """Implementation of a Neurio energy sensor."""

    def __init__(self, data, name, sensor_type, update_call):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._sensor_type = sensor_type
        self.update_sensor = update_call
        self._state = None

        if sensor_type == ACTIVE_TYPE:
            self._unit_of_measurement = POWER_WATT
        elif sensor_type == DAILY_TYPE:
            self._unit_of_measurement = ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data, update state."""
        self.update_sensor()

        if self._name == ACTIVE_NAME:
            self._state = self._data.active_power
        elif self.name == DAILY_NAME:
            self._state = self._data.daily_usage
        elif self.name == GENERATION_NAME:
            self._state = self._data.active_generation
        elif self.name == GENERATION_DAILY_NAME:
            self._state = self._data.daily_generation
        elif self.name == NET_CONSUMPTION:
            self._state = self._data.net_consumption
        elif self.name == JSON_DATASET:
            self._state = self._data.dataset
