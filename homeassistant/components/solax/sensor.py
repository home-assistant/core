"""Support for Solax inverter via local API."""
import asyncio
from datetime import timedelta

from solax import real_time_api
from solax.inverter import InverterError

from homeassistant import config_entries, core
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
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
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

DEFAULT_PORT = 80
SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Entry setup."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    api = await real_time_api(
        config[CONF_IP_ADDRESS], config[CONF_PORT], config[CONF_PASSWORD]
    )
    resp = await api.get_data()
    serial = resp.serial_number
    endpoint = RealTimeDataEndpoint(hass, api)
    hass.async_add_job(endpoint.async_refresh)
    async_track_time_interval(hass, endpoint.async_refresh, SCAN_INTERVAL)
    devices = []
    for sensor, (idx, unit) in api.inverter.sensor_map().items():
        device_class = state_class = None
        if unit == "C":
            device_class = DEVICE_CLASS_TEMPERATURE
            state_class = STATE_CLASS_MEASUREMENT
            unit = TEMP_CELSIUS
        elif unit == "kWh":
            device_class = DEVICE_CLASS_ENERGY
            state_class = STATE_CLASS_TOTAL_INCREASING
        elif unit == "V":
            device_class = DEVICE_CLASS_VOLTAGE
            state_class = STATE_CLASS_MEASUREMENT
        elif unit == "A":
            device_class = DEVICE_CLASS_CURRENT
            state_class = STATE_CLASS_MEASUREMENT
        elif unit == "W":
            device_class = DEVICE_CLASS_POWER
            state_class = STATE_CLASS_MEASUREMENT
        elif unit == "%":
            device_class = DEVICE_CLASS_BATTERY
            state_class = STATE_CLASS_MEASUREMENT
        uid = f"{serial}-{idx}"
        devices.append(Inverter(uid, serial, sensor, unit, state_class, device_class))
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
    ):
        """Initialize an inverter sensor."""
        self.uid = uid
        self.serial = serial
        self.key = key
        self.value = None
        self.unit = unit
        self._attr_state_class = state_class
        self._attr_device_class = device_class

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
    def should_poll(self):
        """No polling needed."""
        return False
