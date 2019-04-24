"""Support for TekSavvy Bandwidth Monitor."""
from datetime import timedelta
import logging
import async_timeout

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY, CONF_MONITORED_VARIABLES, CONF_NAME)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'TekSavvy'
CONF_TOTAL_BANDWIDTH = 'total_bandwidth'

GIGABYTES = 'GB'  # type: str
PERCENT = '%'  # type: str

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
REQUEST_TIMEOUT = 5  # seconds

SENSOR_TYPES = {
    'usage': ['Usage Ratio', PERCENT, 'mdi:percent'],
    'usage_gb': ['Usage', GIGABYTES, 'mdi:download'],
    'limit': ['Data limit', GIGABYTES, 'mdi:download'],
    'onpeak_download': ['On Peak Download', GIGABYTES, 'mdi:download'],
    'onpeak_upload': ['On Peak Upload', GIGABYTES, 'mdi:upload'],
    'onpeak_total': ['On Peak Total', GIGABYTES, 'mdi:download'],
    'offpeak_download': ['Off Peak download', GIGABYTES, 'mdi:download'],
    'offpeak_upload': ['Off Peak Upload', GIGABYTES, 'mdi:upload'],
    'offpeak_total': ['Off Peak Total', GIGABYTES, 'mdi:download'],
    'onpeak_remaining': ['Remaining', GIGABYTES, 'mdi:download']
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
    vol.Required(CONF_TOTAL_BANDWIDTH): cv.positive_int,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the sensor platform."""
    websession = async_get_clientsession(hass)
    apikey = config.get(CONF_API_KEY)
    bandwidthcap = config.get(CONF_TOTAL_BANDWIDTH)

    ts_data = TekSavvyData(hass.loop, websession, apikey, bandwidthcap)
    ret = await ts_data.async_update()
    if ret is False:
        _LOGGER.error("Invalid Teksavvy API key: %s", apikey)
        return

    name = config.get(CONF_NAME)
    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(TekSavvySensor(ts_data, variable, name))
    async_add_entities(sensors, True)


class TekSavvySensor(Entity):
    """Representation of TekSavvy Bandwidth sensor."""

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

    async def async_update(self):
        """Get the latest data from TekSavvy and update the state."""
        await self.teksavvydata.async_update()
        if self.type in self.teksavvydata.data:
            self._state = round(self.teksavvydata.data[self.type], 2)


class TekSavvyData:
    """Get data from TekSavvy API."""

    def __init__(self, loop, websession, api_key, bandwidth_cap):
        """Initialize the data object."""
        self.loop = loop
        self.websession = websession
        self.api_key = api_key
        self.bandwidth_cap = bandwidth_cap
        # Set unlimited users to infinite, otherwise the cap.
        self.data = {"limit": self.bandwidth_cap} if self.bandwidth_cap > 0 \
            else {"limit": float('inf')}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the TekSavvy bandwidth data from the web service."""
        headers = {"TekSavvy-APIKey": self.api_key}
        _LOGGER.debug("Updating TekSavvy data")
        url = "https://api.teksavvy.com/"\
              "web/Usage/UsageSummaryRecords?$filter=IsCurrent%20eq%20true"
        with async_timeout.timeout(REQUEST_TIMEOUT, loop=self.loop):
            req = await self.websession.get(url, headers=headers)
        if req.status != 200:
            _LOGGER.error("Request failed with status: %u", req.status)
            return False

        try:
            data = await req.json()
            for (api, ha_name) in API_HA_MAP:
                self.data[ha_name] = float(data["value"][0][api])
            on_peak_download = self.data["onpeak_download"]
            on_peak_upload = self.data["onpeak_upload"]
            off_peak_download = self.data["offpeak_download"]
            off_peak_upload = self.data["offpeak_upload"]
            limit = self.data["limit"]
            # Support "unlimited" users
            if self.bandwidth_cap > 0:
                self.data["usage"] = 100*on_peak_download/self.bandwidth_cap
            else:
                self.data["usage"] = 0
            self.data["usage_gb"] = on_peak_download
            self.data["onpeak_total"] = on_peak_download + on_peak_upload
            self.data["offpeak_total"] =\
                off_peak_download + off_peak_upload
            self.data["onpeak_remaining"] = limit - on_peak_download
            return True
        except ValueError:
            _LOGGER.error("JSON Decode Failed")
            return False
