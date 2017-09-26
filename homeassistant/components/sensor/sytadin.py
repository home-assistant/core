"""
Support for Sytadin Traffic, French Traffic Supervision.

Systadin website : http://www.sytadin.fr

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sytadin/
"""
import logging

from datetime import timedelta
import voluptuous as vol

from homeassistant.const import (LENGTH_KILOMETERS, CONF_NAME)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['lxml==4.0.0']

SYSTADIN = 'http://www.sytadin.fr/sys/barometres_de_la_circulation.jsp.html'

TRAFFIC_JAM_XPATH = '//*[@id="main_content"]/div[1]/div/span[3]/text()'
MEAN_VELOCITY_XPATH = '//*[@id="main_content"]/div[2]/div/span[3]/text()'
CONGESTION_XPATH = '//*[@id="main_content"]/div[3]/div/span[3]/text()'

TRAFFIC_JAM_REGEX = '([0-9]+)'
MEAN_VELOCITY_REGEX = '([0-9]+)'
CONGESTION_REGEX = '([0-9]+.[0-9]+)'

CONF_MONITORED_CONDITION = 'monitored_condition'
OPTION_TRAFFIC_JAM = 'traffic_jam'
OPTION_MEAN_VELOCITY = 'mean_velocity'
OPTION_CONGESTION = 'congestion'
CONF_UPDATE_INTERVAL = 'update_interval'

SENSOR_TYPES = {
    OPTION_TRAFFIC_JAM: ('Sytadin Traffic Jam', LENGTH_KILOMETERS),
    OPTION_MEAN_VELOCITY: ('Sytadin Mean Velocity', LENGTH_KILOMETERS+'/h'),
    OPTION_CONGESTION: ('Sytadin Congestion', '')
}

TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_CONDITION): cv.string,
    vol.Optional(CONF_NAME): cv.string,
    # vol.Optional(CONF_MONITORED_CONDITION, default=''):
    #     vol.All(cv.string, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_UPDATE_INTERVAL, default=timedelta(seconds=300)): (
        vol.All(cv.time_period, cv.positive_timedelta)),
})

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the sensor platform."""
    options = [
        it.strip() for it in config.get(CONF_MONITORED_CONDITION).split(',')
    ]

    name = config.get(CONF_NAME)

    if OPTION_TRAFFIC_JAM in options:
        if not name:
            name = SENSOR_TYPES.get(OPTION_TRAFFIC_JAM)[0]
        add_devices([
            SytadinSensor(name, SYSTADIN, TRAFFIC_JAM_XPATH,
                          TRAFFIC_JAM_REGEX,
                          SENSOR_TYPES.get(OPTION_TRAFFIC_JAM)[1],
                          config.get(CONF_UPDATE_INTERVAL))
            ])
    if OPTION_MEAN_VELOCITY in options:
        if not name:
            name = SENSOR_TYPES.get(OPTION_MEAN_VELOCITY)[0]
        add_devices([
            SytadinSensor(name, SYSTADIN,
                          MEAN_VELOCITY_XPATH, MEAN_VELOCITY_REGEX,
                          SENSOR_TYPES.get(OPTION_MEAN_VELOCITY)[1]+'/h',
                          config.get(CONF_UPDATE_INTERVAL))
            ])
    if OPTION_CONGESTION in options:
        if not name:
            name = SENSOR_TYPES.get(OPTION_CONGESTION)[0]
        add_devices([
            SytadinSensor(name, SYSTADIN, CONGESTION_XPATH,
                          CONGESTION_REGEX,
                          SENSOR_TYPES.get(OPTION_CONGESTION)[1],
                          config.get(CONF_UPDATE_INTERVAL))
            ])


class SytadinSensor(Entity):
    """Sytadin Sensor."""

    def __init__(self, name, url, xpath, regex, unit, interval):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._url = url
        self._xpath = xpath
        self._regex = regex
        self._unit = unit
        self.update = Throttle(interval)(self._update)

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
        """Return the unit of measurement."""
        return self._unit

    def _update(self):
        """Fetch new state data for the sensor."""
        import requests
        import re
        from lxml import etree

        html = requests.get(self._url, timeout=TIMEOUT)
        tree = etree.HTML(html.content)
        extract_xpath = tree.xpath(self._xpath)

        self._state = re.search(self._regex, extract_xpath[0]).group()
