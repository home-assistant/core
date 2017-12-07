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
from homeassistant.util.json import load_json, save_json
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/jamespcole/home-assistant-nzb-clients/'
                'archive/616cad59154092599278661af17e2a9f2cf5e2a9.zip'
                '#python-sabnzbd==0.1']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None

CONFIG_FILE = 'sabnzbd.conf'
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
    'queue_count': ['Queue Count', None],
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


def _check_sabnzbd(sab_api, base_url, api_key):
    """Check if we can reach SABnzbd."""
    from pysabnzbd import SabnzbdApiException
    sab_api = sab_api(base_url, api_key)

    try:
        sab_api.check_available()
    except SabnzbdApiException:
        _LOGGER.error("Connection to SABnzbd API failed")
        return False
    return True


def setup_sabnzbd(base_url, apikey, name, hass, config, add_devices, sab_api):
    """Set up polling from SABnzbd and sensors."""
    sab_api = sab_api(base_url, apikey)
    # Add minimal info to the front end
    monitored = config.get(CONF_MONITORED_VARIABLES, ['current_status'])

    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(
        MIN_TIME_BETWEEN_UPDATES)(sab_api.refresh_queue)

    devices = []
    for variable in monitored:
        devices.append(SabnzbdSensor(variable, sab_api, name))

    add_devices(devices)


def request_configuration(host, name, hass, config, add_devices, sab_api):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(_CONFIGURING[host],
                                   'Failed to register, please try again.')

        return

    def sabnzbd_configuration_callback(data):
        """Handle configuration changes."""
        api_key = data.get('api_key')
        if _check_sabnzbd(sab_api, host, api_key):
            setup_sabnzbd(host, api_key, name,
                          hass, config, add_devices, sab_api)

            def success():
                """Set up was successful."""
                conf = load_json(hass.config.path(CONFIG_FILE))
                conf[host] = {'api_key': api_key}
                save_json(hass.config.path(CONFIG_FILE), conf)
                req_config = _CONFIGURING.pop(host)
                hass.async_add_job(configurator.request_done, req_config)

            hass.async_add_job(success)

    _CONFIGURING[host] = configurator.request_config(
        DEFAULT_NAME,
        sabnzbd_configuration_callback,
        description=('Enter the API Key'),
        submit_caption='Confirm',
        fields=[{
            'id': 'api_key',
            'name': 'API Key',
            'type': ''}]
    )


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SABnzbd platform."""
    from pysabnzbd import SabnzbdApi

    if discovery_info is not None:
        host = discovery_info.get(CONF_HOST)
        port = discovery_info.get(CONF_PORT)
        name = DEFAULT_NAME
        use_ssl = discovery_info.get('properties', {}).get('https', '0') == '1'
    else:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        name = config.get(CONF_NAME, DEFAULT_NAME)
        use_ssl = config.get(CONF_SSL)

    uri_scheme = 'https://' if use_ssl else 'http://'
    base_url = "{}{}:{}/".format(uri_scheme, host, port)
    api_key = config.get(CONF_API_KEY)

    if not api_key:
        conf = load_json(hass.config.path(CONFIG_FILE))
        if conf.get(base_url, {}).get('api_key'):
            api_key = conf[base_url]['api_key']

    if not _check_sabnzbd(SabnzbdApi, base_url, api_key):
        request_configuration(base_url, name, hass, config,
                              add_devices, SabnzbdApi)
        return

    setup_sabnzbd(base_url, api_key, name, hass,
                  config, add_devices, SabnzbdApi)


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
            elif self.type == 'queue_count':
                self._state = self.sabnzb_client.queue.get('noofslots_total')
            else:
                self._state = 'Unknown'
