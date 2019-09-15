from logging import getLogger
from datetime import timedelta

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_NAME,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.util import Throttle

_LOGGER = getLogger(__name__)

AQI_SCALE = {
    "cn": [0, 50, 100, 150, 200, 300, 400, 500],
    "in": [0, 50, 100, 200, 300, 400, 500],
    "us": [0, 50, 100, 150, 200, 300, 500],
}

AQI_LEVEL = {
    "cn": [
        {"label": "Good", "icon": "mdi:emoticon-excited"},
        {"label": "Satisfactory", "icon": "mdi:emoticon-cool"},
        {"label": "Moderate", "icon": "mdi:emoticon-happy"},
        {"label": "Unhealthy for sensitive groups", "icon": "mdi:emoticon-neutral"},
        {"label": "Unhealthy", "icon": "mdi:emoticon-sad"},
        {"label": "Very unhealthy", "icon": "mdi:emoticon-dead"},
        {"label": "Hazardous", "icon": "mdi:biohazard"}
    ],
    "in": [
        {"label": "Good", "icon": "mdi:emoticon-excited"},
        {"label": "Satisfactory", "icon": "mdi:emoticon-happy"},
        {"label": "Moderately polluted", "icon": "mdi:emoticon-neutral"},
        {"label": "Poor", "icon": "mdi:emoticon-sad"},
        {"label": "Very poor", "icon": "mdi:emoticon-dead"},
        {"label": "Severe", "icon": "mdi:biohazard"}
    ],
    "us": [
        {"label": "Good", "icon": "mdi:emoticon-excited"},
        {"label": "Moderate", "icon": "mdi:emoticon-happy"},
        {"label": "Unhealthy for sensitive groups", "icon": "mdi:emoticon-neutral"},
        {"label": "Unhealthy", "icon": "mdi:emoticon-sad"},
        {"label": "Very unhealthy", "icon": "mdi:emoticon-dead"},
        {"label": "Hazardous", "icon": "mdi:biohazard"}
    ],
}

SENSORS = {
    "rpm25c": {"name": "PM2.5", "icon": "mdi:weather-windy"},
    "rpm10c": {"name": "PM10", "icon": "mdi:weather-windy"},
    "rtvoc": {"name": "TVOC", "icon": "mdi:weather-windy"},
    "rtemp": {"name": "Temperature", "icon": "mdi:temperature-celsius"},
    "rhumid": {"name": "Humidity", "icon": "mdi:water"},
    "aqi": {"name": "Air Quality Index", "icon": "mdi:chart-line"},
    "aqi_level": {"name": "Air Quality Level", "icon": "mdi:gauge"},
    "aqi_pollutant": {"name": "Main Pollutant", "icon": "mdi:chemical-weapon"},
}

AVAILABLE_AQI_STANDARDS = ['us', 'cn', 'in']
AVAILABLE_UNITS = ['x', '%', 'C', 'F', 'mg/m³', 'µg/m³', 'ppm', 'ppb']
AVAILABLE_DEVICE_TYPES = ['laseregg', 'sensedge']

CONF_AQI_STANDARD = 'aqi_standard'
CONF_PREFERRED_UNITS = 'preferred_units'

DEFAULT_AQI_STANDARD = 'us'
DEFAULT_PREFERRED_UNIT= []
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

KAITERRA_DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_DEVICE_ID): cv.string,
    vol.Required(CONF_TYPE): vol.In(AVAILABLE_DEVICE_TYPES),
    vol.Optional(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [KAITERRA_DEVICE_SCHEMA]),
        vol.Optional(CONF_AQI_STANDARD, default=DEFAULT_AQI_STANDARD): vol.In(AVAILABLE_AQI_STANDARDS),
        vol.Optional(CONF_PREFERRED_UNITS, default=DEFAULT_PREFERRED_UNIT): vol.All(cv.ensure_list, [vol.In(AVAILABLE_UNITS)]),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the air_quality kaiterra sensor."""
    from kaiterra_async_client import KaiterraAPIClient, AQIStandard, Units
    
    api_key = config.get(CONF_API_KEY)
    aqi_standard = config.get(CONF_AQI_STANDARD)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    devices = config.get(CONF_DEVICES)
    units = [Units.from_str(unit) for unit in config.get(CONF_PREFERRED_UNITS)]

    api = KaiterraAPIClient(aiohttp_client.async_get_clientsession(hass), api_key=api_key, aqi_standard=AQIStandard.from_str(aqi_standard), preferred_units=units)
    data = KaiterraData(api, devices, aqi_standard, scan_interval)

    await data.async_update()

    sensors = []
    for device in devices:
        device_id, device_name, device_type = device.get(CONF_DEVICE_ID), device.get(CONF_NAME), device.get(CONF_TYPE)
        for kind, sensor in SENSORS.items():
            sensors.append(
                KaiterraSensor(data, f"{device_name if device_name else device_type} {sensor['name']}", device_id, kind, sensor['icon'])
            )

    async_add_entities(sensors, True)


class KaiterraSensor(Entity):
    """Implementation of a Kaittera sensor."""

    def __init__(self, data, name, device_id, kind, icon):
        """Initialize the sensor."""
        self._data = data
        self._name = name
        self._icon = icon
        self._type = kind
        self._device_id = device_id
        self._state = None
        self._unit = None

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._data.result.get(self._device_id))

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return f"{self._device_id}_{self._type}"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_update(self):
        """Update the sensor."""
        await self._data.async_update()
        data = self._data.result.get(self._device_id)

        if not data:
            return

        sensor = data.get(self._type)
        if not sensor:
            return

        if self._type == 'aqi_level':
            level = sensor.get('value')
            if level:
                self._state = level.get('label')
                self._icon = level.get('icon')
        else:
            self._state = sensor.get('value')
            
            if sensor.get('units'):
                value = sensor.get('units').value
                self._unit = '°' + value if value in ['F', 'C'] else value
            else:
                self._unit =  None

class KaiterraData:
    """Get data from Kaiterra API."""

    def __init__(self, api, devices, aqi_standard, throttle):
        """Initialize the data object."""
        self._api = api
        self._devices_ids = [device.get(CONF_DEVICE_ID) for device in devices]
        self._devices = [f'/{device.get(CONF_TYPE)}s/{device.get(CONF_DEVICE_ID)}' for device in devices]
        self._scale = AQI_SCALE[aqi_standard]
        self._level = AQI_LEVEL[aqi_standard]
        self.result = {}
        self.async_update = Throttle(throttle)(self._async_update)

    async def _async_update(self) -> None:
        """Get the data from Kaiterra API."""

        try:
            with async_timeout.timeout(10):
                data = await self._api.get_latest_sensor_readings(self._devices)
                _LOGGER.debug('New data retrieved: %s', data)
        except:
            _LOGGER.debug("Couldn't fetch data")
            self.result = {}
            return False
        
        try:
            self.result = {}
            for i in range(len(data)):
                device = data[i]

                if not device:
                    self.result[self._devices_ids[i]] = {}
                    continue
                
                aqi, main_pollutant = None, None
                for sensor in device:
                    points = device.get(sensor).get('points')

                    if not points or len(points) == 0:
                        continue
                    
                    point = points[0]
                    device[sensor]['value'] = point.get('value')

                    if 'aqi' not in point:
                        continue

                    device[sensor]['aqi'] = point.get('aqi')
                    if not aqi or aqi < point.get('aqi'):
                        aqi = point['aqi']
                        main_pollutant = SENSORS[sensor]['name']

                level = None
                for j in range(1, len(self._scale)):
                    if aqi <= self._scale[j]:
                        level = self._level[j-1]
                        break

                device['aqi'] = {'value': aqi}
                device['aqi_level'] = {'value': level}
                device['aqi_pollutant'] = {'value': main_pollutant}

                self.result[self._devices_ids[i]] = device
        except IndexError as err:
            _LOGGER.error('Parsing error %s', err)
            return False
        return True