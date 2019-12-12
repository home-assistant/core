"""Support for iammeter via local API."""
import asyncio

from datetime import timedelta
import logging
import iammeter
from iammeter import power_meter
from iammeter.power_meter import IamMeterError
import requests
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PORT, CONF_NAME, CONF_HOST
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup."""
    try:
        base = "http://admin:admin@{}:{}/monitorjson"
        url = base.format(config[CONF_HOST], config[CONF_PORT])
        resp = requests.get(url)
        json_data = resp.json()
        _LOGGER.error(json_data)
        if "SN" in json_data:
            serial = json_data["SN"]
        if "mac" in json_data:
            mac = json_data["mac"]
    except Exception as err:
        _LOGGER.error(err)
        raise PlatformNotReady
    devices = []
    if "data" in json_data:
        _LOGGER.info("3162")
        api = iammeter.RealTimeAPI(
            power_meter.WEM3162(config[CONF_HOST], config[CONF_PORT])
        )
        for sensor, (idx, unit) in api.iammeter.sensor_map().items():
            uid = f"{config[CONF_NAME]}-{idx}"
            devices.append(IamMeter(uid, "", sensor, unit, config[CONF_NAME]))
    if "Data" in json_data:
        _LOGGER.info("3080")
        api = iammeter.RealTimeAPI(
            power_meter.WEM3080(config[CONF_HOST], config[CONF_PORT])
        )
        for sensor, (idx, unit) in api.iammeter.sensor_map().items():
            uid = f"{config[CONF_NAME]}-{mac}-{serial}-{idx}"
            devices.append(IamMeter(uid, serial, sensor, unit, config[CONF_NAME]))
    if "Datas" in json_data:
        _LOGGER.info("3080T")
        api = iammeter.RealTimeAPI(
            power_meter.WEM3080T(config[CONF_HOST], config[CONF_PORT])
        )
        for sensor, (row, idx, unit) in api.iammeter.sensor_map().items():
            uid = f"{config[CONF_NAME]}-{mac}-{serial}-{row}-{idx}"
            devices.append(IamMeter(uid, serial, sensor, unit, config[CONF_NAME]))

    endpoint = RealTimeDataEndpoint(hass, api)
    endpoint.ready.set()
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    endpoint.sensors = devices
    async_add_entities(devices)


class RealTimeDataEndpoint:
    """Representation of a Sensor."""

    def __init__(self, hass, api):
        """Initialize the sensor."""
        self.hass = hass
        self.api = api
        self.ready = asyncio.Event()
        self.sensors = []

    async def async_refresh(self, now=None):
        """Fetch new state data for the sensor.This is the only method that should fetch new data for Home Assistant."""
        try:
            api_response = await self.api.get_data()
            self.ready.set()
        except IamMeterError:
            if now is not None:
                self.ready.clear()
                return
            raise PlatformNotReady
        data = api_response.data
        for sensor in self.sensors:
            if sensor.key in data:
                sensor.value = data[sensor.key]
                sensor.schedule_update_ha_state()


class IamMeter(Entity):
    """Class for a sensor."""

    def __init__(self, uid, serial, key, unit, dev_name):
        """Initialize an iammeter sensor."""
        self.uid = uid
        self.serial = serial
        self.key = key
        self.value = None
        self.unit = unit
        self.dev_name = dev_name
        self.dev_type = "WEM3080"

    @property
    def state(self):
        """State of this iammeter attribute."""
        return self.value

    @property
    def unique_id(self):
        """Return unique id."""
        return self.uid

    @property
    def name(self):
        """Name of this iammeter attribute."""
        return f"{self.dev_name} {self.key}"

    @property
    def icon(self):
        """Icon for each sensor."""
        return "mdi:flash"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit

    @property
    def should_poll(self):
        """No polling needed."""
        return False
