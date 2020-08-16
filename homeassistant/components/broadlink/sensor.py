"""Support for the Broadlink RM2 Pro (only temperature) and A1 devices."""
from datetime import timedelta
from ipaddress import ip_address
import logging

import broadlink as blk
from broadlink.exceptions import BroadlinkException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TYPE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from . import hostname, mac_address
from .const import (
    A1_TYPES,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT,
    RM4_TYPES,
    RM_TYPES,
)
from .device import BroadlinkDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)

SENSOR_TYPES = {
    "temperature": ["Temperature", TEMP_CELSIUS],
    "air_quality": ["Air Quality", " "],
    "humidity": ["Humidity", UNIT_PERCENTAGE],
    "light": ["Light", " "],
    "noise": ["Noise", " "],
}

DEVICE_TYPES = A1_TYPES + RM_TYPES + RM4_TYPES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.Coerce(str),
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Required(CONF_HOST): vol.All(vol.Any(hostname, ip_address), cv.string),
        vol.Required(CONF_MAC): mac_address,
        vol.Optional(CONF_TYPE, default=DEVICE_TYPES[0]): vol.In(DEVICE_TYPES),
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Broadlink device sensors."""
    host = config[CONF_HOST]
    mac_addr = config[CONF_MAC]
    model = config[CONF_TYPE]
    name = config[CONF_NAME]
    timeout = config[CONF_TIMEOUT]
    update_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    if model in RM4_TYPES:
        api = blk.rm4((host, DEFAULT_PORT), mac_addr, None)
        check_sensors = api.check_sensors
    else:
        api = blk.a1((host, DEFAULT_PORT), mac_addr, None)
        check_sensors = api.check_sensors_raw

    api.timeout = timeout
    device = BroadlinkDevice(hass, api)

    connected = await device.async_connect()
    if not connected:
        raise PlatformNotReady

    broadlink_data = BroadlinkData(device, check_sensors, update_interval)
    sensors = [
        BroadlinkSensor(name, broadlink_data, variable)
        for variable in config[CONF_MONITORED_CONDITIONS]
    ]
    async_add_entities(sensors, True)


class BroadlinkSensor(Entity):
    """Representation of a Broadlink device sensor."""

    def __init__(self, name, broadlink_data, sensor_type):
        """Initialize the sensor."""
        self._name = f"{name} {SENSOR_TYPES[sensor_type][0]}"
        self._state = None
        self._type = sensor_type
        self._broadlink_data = broadlink_data
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._broadlink_data.device.available

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    async def async_update(self):
        """Get the latest data from the sensor."""
        await self._broadlink_data.async_update()
        self._state = self._broadlink_data.data.get(self._type)


class BroadlinkData:
    """Representation of a Broadlink data object."""

    def __init__(self, device, check_sensors, interval):
        """Initialize the data object."""
        self.device = device
        self.check_sensors = check_sensors
        self.data = {}
        self._schema = vol.Schema(
            {
                vol.Optional("temperature"): vol.Range(min=-50, max=150),
                vol.Optional("humidity"): vol.Range(min=0, max=100),
                vol.Optional("light"): vol.Any(0, 1, 2, 3),
                vol.Optional("air_quality"): vol.Any(0, 1, 2, 3),
                vol.Optional("noise"): vol.Any(0, 1, 2),
            }
        )
        self.async_update = Throttle(interval)(self._async_fetch_data)

    async def _async_fetch_data(self):
        """Fetch sensor data."""
        for _ in range(DEFAULT_RETRY):
            try:
                data = await self.device.async_request(self.check_sensors)
            except BroadlinkException:
                return
            try:
                data = self._schema(data)
            except (vol.Invalid, vol.MultipleInvalid):
                continue
            else:
                self.data = data
                return

        _LOGGER.debug("Failed to update sensors: Device returned malformed data")
