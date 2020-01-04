"""Support for iammeter via local API."""
import asyncio
from datetime import timedelta
import logging

from iammeter import real_time_api
from iammeter.power_meter import IamMeterError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 80

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default="IamMeter"): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup."""
    api = await real_time_api(config[CONF_HOST], config[CONF_PORT])
    endpoint = RealTimeDataEndpoint(hass, api)
    devices = []
    for sensor, (row, idx, unit) in api.iammeter.sensor_map().items():
        uid = f"{config[CONF_NAME]}-{api.iammeter.mac}-{api.iammeter.serial_number}-{row}-{idx}"
        devices.append(
            IamMeter(uid, api.iammeter.serial_number, sensor, unit, config[CONF_NAME])
        )
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
