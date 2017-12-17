"""
Support for TekSavvy.

Get bandwidth comsumption data using Teksavvy API
You can get your API key here:
https://myaccount.teksavvy.com/ApiKey/ApiKeyManagement

TekSavvy only counts download only as part of the bandwidth

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.teksavvy/
"""
import logging
from datetime import timedelta
import http.client
import json
import requests
import voluptuous as vol
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_API_KEY, CONF_NAME, CONF_MONITORED_VARIABLES)

from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = 'TekSavvy'
CONF_TOTAL_BANDWIDTH = 'total_bandwidth'

GIGABITS = 'Gb'  # type: str
PERCENT = '%'  # type: str

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


SENSOR_TYPES = {
    'usage': ['Usage', PERCENT, 'mdi:percent'],
    'usage_gb': ['Usage', GIGABITS, 'mdi:download'],
    'limit': ['Data limit', GIGABITS, 'mdi:download'],
    'onpeak_download': ['On Peak Download', GIGABITS, 'mdi:download'],
    'onpeak_upload': ['On Peak Upload ', GIGABITS, 'mdi:upload'],
    'onpeak_total': ['On Peak Total', GIGABITS, 'mdi:download'],
    'offpeak_download': ['Off Peak download', GIGABITS, 'mdi:download'],
    'offpeak_upload': ['Off Peak Upload', GIGABITS, 'mdi:upload'],
    'offpeak_total': ['Off Peak Total', GIGABITS, 'mdi:download'],
    'onpeak_remaining': ['Remaining', GIGABITS, 'mdi:download']
}

API_HA_MAP = (
    ('OnPeakDownload', 'onpeak_download'),
    ('OnPeakUpload', 'onpeak_upload'),
    ('OffPeakDownload', 'offpeak_download'),
    ('OffPeakUpload', 'offpeak_upload'))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_TOTAL_BANDWIDTH): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    apikey = config.get(CONF_API_KEY)
    bandwidthcapstr = config.get(CONF_TOTAL_BANDWIDTH)

    try:
        bandwidthcap = int(bandwidthcapstr)
        teksavvy_data = TekSavvyData(apikey, bandwidthcap)
        teksavvy_data.update()
    except ValueError as error:
        _LOGGER.error("Failed conversion %s %s", CONF_TOTAL_BANDWIDTH, error)
    except requests.exceptions.HTTPError as error:
        _LOGGER.error("Fail to fetch data %s", error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(TekSavvySensor(teksavvy_data, variable, name))

    add_devices(sensors, True)


class TekSavvySensor(Entity):
    """TekSavvy Bandwidth sensor."""

    def __init__(self, teksavvydata, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.teksavvydata = teksavvydata
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

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
        return self._icon

    def update(self):
        """Get the latest data from TekSavvy and update the state."""
        self.teksavvydata.update()
        if self.type in self.teksavvydata.data:
            self._state = round(self.teksavvydata.data[self.type], 2)


class TekSavvyData(object):
    """Get data from TekSavvy API."""

    def __init__(self, api_key, bandwidth_cap):
        """Initialize the data object."""
        self.api_key = api_key
        self.bandwidth_cap = bandwidth_cap
        self.data = dict()
        self.data["limit"] = self.bandwidth_cap

    def _fetch_data(self):
        headers = {"TekSavvy-APIKey": self.api_key}
        conn = http.client.HTTPSConnection("api.teksavvy.com")
        req = '/web/Usage/UsageSummaryRecords?$filter=IsCurrent%20eq%20true'
        conn.request('GET', req, '', headers)
        response = conn.getresponse()
        jsonData = response.read().decode("utf-8")
        data = json.loads(jsonData)
        for (Api, Ha) in API_HA_MAP:
            self.data[Ha] = float(data["value"][0][Api])
        OnPeakDownload = self.data["onpeak_download"]
        OnPeakUpload = self.data["onpeak_upload"]
        OffPeakDownload = self.data["offpeak_download"]
        OffPeakUpload = self.data["offpeak_upload"]
        Limit = self.data["limit"]
        self.data["usage"] = 100*OnPeakDownload/self.bandwidth_cap
        self.data["usage_gb"] = OnPeakDownload
        self.data["onpeak_total"] = OnPeakDownload + OnPeakUpload
        self.data["offpeak_total"] = OffPeakDownload + OffPeakUpload
        self.data["onpeak_remaining"] = Limit - OnPeakUpload

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Return the latest collected data from TekSavvy."""
        self._fetch_data()
