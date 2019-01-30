"""
Support for AirVisual air quality sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.airvisual/
"""
from logging import getLogger
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.airvisual import (
    DATA_CLIENT, DOMAIN, SENSOR_LOCALES, TOPIC_UPDATE)
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

_LOGGER = getLogger(__name__)

ATTR_CITY = 'city'
ATTR_COUNTRY = 'country'
ATTR_POLLUTANT_SYMBOL = 'pollutant_symbol'
ATTR_POLLUTANT_UNIT = 'pollutant_unit'
ATTR_REGION = 'region'

DEFAULT_ATTRIBUTION = "Data provided by AirVisual"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=10)

MASS_PARTS_PER_MILLION = 'ppm'
MASS_PARTS_PER_BILLION = 'ppb'
VOLUME_MICROGRAMS_PER_CUBIC_METER = 'µg/m3'

SENSOR_TYPE_LEVEL = 'air_pollution_level'
SENSOR_TYPE_AQI = 'air_quality_index'
SENSOR_TYPE_POLLUTANT = 'main_pollutant'
SENSORS = [
    (SENSOR_TYPE_LEVEL, 'Air Pollution Level', 'mdi:gauge', None),
    (SENSOR_TYPE_AQI, 'Air Quality Index', 'mdi:chart-line', 'AQI'),
    (SENSOR_TYPE_POLLUTANT, 'Main Pollutant', 'mdi:chemical-weapon', None),
]

POLLUTANT_LEVEL_MAPPING = [{
    'label': 'Good',
    'icon': 'mdi:emoticon-excited',
    'minimum': 0,
    'maximum': 50
},
                           {
                               'label': 'Moderate',
                               'icon': 'mdi:emoticon-happy',
                               'minimum': 51,
                               'maximum': 100
                           },
                           {
                               'label': 'Unhealthy for sensitive groups',
                               'icon': 'mdi:emoticon-neutral',
                               'minimum': 101,
                               'maximum': 150
                           },
                           {
                               'label': 'Unhealthy',
                               'icon': 'mdi:emoticon-sad',
                               'minimum': 151,
                               'maximum': 200
                           },
                           {
                               'label': 'Very Unhealthy',
                               'icon': 'mdi:emoticon-dead',
                               'minimum': 201,
                               'maximum': 300
                           },
                           {
                               'label': 'Hazardous',
                               'icon': 'mdi:biohazard',
                               'minimum': 301,
                               'maximum': 10000
                           }]

POLLUTANT_MAPPING = {
    'co': {
        'label': 'Carbon Monoxide',
        'unit': MASS_PARTS_PER_MILLION
    },
    'n2': {
        'label': 'Nitrogen Dioxide',
        'unit': MASS_PARTS_PER_BILLION
    },
    'o3': {
        'label': 'Ozone',
        'unit': MASS_PARTS_PER_BILLION
    },
    'p1': {
        'label': 'PM10',
        'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER
    },
    'p2': {
        'label': 'PM2.5',
        'unit': VOLUME_MICROGRAMS_PER_CUBIC_METER
    },
    's2': {
        'label': 'Sulfur Dioxide',
        'unit': MASS_PARTS_PER_BILLION
    },
}


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up an AirVisual sensor based on existing config."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up an AirVisual sensor based on a config entry."""
    airvisual = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    async_add_entities([
        AirVisualSensor(airvisual, kind, name, icon, unit, locale)
        for locale in airvisual.monitored_conditions
        for kind, name, icon, unit in SENSORS
    ], True)


class AirVisualSensor(Entity):
    """Define an AirVisual sensor."""

    def __init__(self, airvisual, kind, name, icon, unit, locale):
        """Initialize."""
        self._airvisual = airvisual
        self._async_unsub_dispatcher_connect = None
        self._attrs = {ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION}
        self._icon = icon
        self._locale = locale
        self._name = name
        self._state = None
        self._type = kind
        self._unit = unit

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        if self._airvisual.show_on_map:
            self._attrs[ATTR_LATITUDE] = self._airvisual.latitude
            self._attrs[ATTR_LONGITUDE] = self._airvisual.longitude
        else:
            self._attrs['lati'] = self._airvisual.latitude
            self._attrs['long'] = self._airvisual.longitude

        return self._attrs

    @property
    def available(self):
        """Return True if entity is available."""
        return bool(self._airvisual.pollution_info)

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def name(self):
        """Return the name."""
        return '{0} {1}'.format(SENSOR_LOCALES[self._locale], self._name)

    @property
    def state(self):
        """Return the state."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        if self._airvisual.city:
            location_id = '{0}, {1}, {2}'.format(
                self._airvisual.city, self._airvisual.state,
                self._airvisual.country)
        else:
            location_id = '{0}, {1}'.format(
                self._airvisual.latitude, self._airvisual.longitude)

        return '{0}_{1}_{2}'.format(location_id, self._locale, self._type)

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def async_update(self):
        """Update the sensor."""
        data = self._airvisual.pollution_info

        if not data:
            return

        if self._type == SENSOR_TYPE_LEVEL:
            aqi = data['aqi{0}'.format(self._locale)]
            [level] = [
                i for i in POLLUTANT_LEVEL_MAPPING
                if i['minimum'] <= aqi <= i['maximum']
            ]
            self._state = level['label']
            self._icon = level['icon']
        elif self._type == SENSOR_TYPE_AQI:
            self._state = data['aqi{0}'.format(self._locale)]
        elif self._type == SENSOR_TYPE_POLLUTANT:
            symbol = data['main{0}'.format(self._locale)]
            self._state = POLLUTANT_MAPPING[symbol]['label']
            self._attrs.update({
                ATTR_POLLUTANT_SYMBOL: symbol,
                ATTR_POLLUTANT_UNIT: POLLUTANT_MAPPING[symbol]['unit']
            })
