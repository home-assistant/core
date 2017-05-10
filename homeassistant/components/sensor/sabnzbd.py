"""
Support for monitoring an SABnzbd NZB client.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sabnzbd/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_API_KEY, CONF_NAME, CONF_PORT, CONF_MONITORED_VARIABLES,
    CONF_SSL)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/jamespcole/home-assistant-nzb-clients/'
                'archive/616cad59154092599278661af17e2a9f2cf5e2a9.zip'
                '#python-sabnzbd==0.1']

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

DEFAULT_NAME = 'SABnzbd'
DEFAULT_PORT = 8080
DEFAULT_SSL = False

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1)

SENSOR_TYPES = {
    'current_status': ['Status', None],
    'speed': ['Speed', 'MB/s'],
    'queue_size': ['Queue', 'MB'],
    'queue_remaining': ['Left', 'MB'],
    'disk_size': ['Disk', 'GB'],
    'disk_free': ['Disk Free', 'GB'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['current_status']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SABnzbd sensors."""
    from pysabnzbd import SabnzbdApi, SabnzbdApiException

    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    monitored_types = config.get(CONF_MONITORED_VARIABLES)
    use_ssl = config.get(CONF_SSL)

    if use_ssl:
        uri_scheme = 'https://'
    else:
        uri_scheme = 'http://'

    base_url = "{}{}:{}/".format(uri_scheme, host, port)

    sab_api = SabnzbdApi(base_url, api_key)

    try:
        sab_api.check_available()
    except SabnzbdApiException:
        _LOGGER.error("Connection to SABnzbd API failed")
        return False

    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(
        MIN_TIME_BETWEEN_UPDATES)(sab_api.refresh_queue)

    devices = []
    for variable in monitored_types:
        devices.append(SabnzbdSensor(variable, sab_api, name))

    add_devices(devices)


class SabnzbdSensor(Entity):
    """Representation of an SABnzbd sensor."""

    def __init__(self, sensor_type, sabnzb_client, client_name):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.sabnzb_client = sabnzb_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

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

    # pylint: disable=no-self-use
    def refresh_sabnzbd_data(self):
        """Call the throttled SABnzbd refresh method."""
        if _THROTTLED_REFRESH is not None:
            from pysabnzbd import SabnzbdApiException
            try:
                _THROTTLED_REFRESH()
            except SabnzbdApiException:
                _LOGGER.exception("Connection to SABnzbd API failed")

    def update(self):
        """Get the latest data and updates the states."""
        self.refresh_sabnzbd_data()

        if self.sabnzb_client.queue:
            if self.type == 'current_status':
                self._state = self.sabnzb_client.queue.get('status')
            elif self.type == 'speed':
                mb_spd = float(self.sabnzb_client.queue.get('kbpersec')) / 1024
                self._state = round(mb_spd, 1)
            elif self.type == 'queue_size':
                self._state = self.sabnzb_client.queue.get('mb')
            elif self.type == 'queue_remaining':
                self._state = self.sabnzb_client.queue.get('mbleft')
            elif self.type == 'disk_size':
                self._state = self.sabnzb_client.queue.get('diskspacetotal1')
            elif self.type == 'disk_free':
                self._state = self.sabnzb_client.queue.get('diskspace1')
            else:
                self._state = 'Unknown'
