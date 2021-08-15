"""Support for Solax inverter via local API."""
import asyncio
from datetime import timedelta

from solax import real_time_api
from solax.inverter import InverterError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    TEMP_CELSIUS,
)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

DEFAULT_PORT = 80

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Platform setup."""
    api = await real_time_api(config[CONF_IP_ADDRESS], config[CONF_PORT])
    endpoint = RealTimeDataEndpoint(hass, api)
    resp = await api.get_data()
    serial = resp.serial_number
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    devices = []
    for sensor, (idx, unit) in api.inverter.sensor_map().items():
        state_class = STATE_CLASS_MEASUREMENT
        if sensor.startswith("Today"):
            last_reset = None
        else:
            last_reset = dt_util.utc_from_timestamp(0)
        device_class = None
        if unit == "C":
            unit = TEMP_CELSIUS
            device_class = DEVICE_CLASS_TEMPERATURE
        elif unit == "kWh":
            device_class = DEVICE_CLASS_ENERGY
        elif unit == "V":
            device_class = DEVICE_CLASS_VOLTAGE
        elif unit == "A":
            device_class = DEVICE_CLASS_CURRENT
        elif unit == "W":
            device_class = DEVICE_CLASS_POWER
        elif unit == "%":
            device_class = DEVICE_CLASS_BATTERY
        uid = f"{serial}-{idx}"
        devices.append(
            Inverter(uid, serial, sensor, unit, state_class, device_class, last_reset)
        )
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
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        try:
            api_response = await self.api.get_data()
            self.ready.set()
        except InverterError as err:
            if now is not None:
                self.ready.clear()
                return
            raise PlatformNotReady from err
        data = api_response.data
        for sensor in self.sensors:
            if sensor.key in data:
                sensor.value = data[sensor.key]
                sensor.async_schedule_update_ha_state()


class Inverter(SensorEntity):
    """Class for a sensor."""

    def __init__(
        self,
        uid,
        serial,
        key,
        unit,
        state_class=None,
        device_class=None,
        last_reset=None,
    ):
        """Initialize an inverter sensor."""
        self.uid = uid
        self.serial = serial
        self.key = key
        self.value = None
        self.unit = unit
        self._state_class = state_class
        self._device_class = device_class
        self._last_reset = last_reset

    @property
    def native_value(self):
        """State of this inverter attribute."""
        return self.value

    @property
    def unique_id(self):
        """Return unique id."""
        return self.uid

    @property
    def name(self):
        """Name of this inverter attribute."""
        return f"Solax {self.serial} {self.key}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit

    @property
    def state_class(self):
        """Return the state class."""
        return self._state_class

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def last_reset(self):
        """Return the last reset."""
        return self._last_reset

    @property
    def should_poll(self):
        """No polling needed."""
        return False
