"""
Support for monitoring an SABnzbd NZB client.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sabnzbd/
"""
import logging
from datetime import timedelta

from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['https://github.com/jamespcole/home-assistant-nzb-clients/'
                'archive/616cad59154092599278661af17e2a9f2cf5e2a9.zip'
                '#python-sabnzbd==0.1']

SENSOR_TYPES = {
    'current_status': ['Status', None],
    'speed': ['Speed', 'MB/s'],
    'queue_size': ['Queue', 'MB'],
    'queue_remaining': ['Left', 'MB'],
    'disk_size': ['Disk', 'GB'],
    'disk_free': ['Disk Free', 'GB'],
}

_LOGGER = logging.getLogger(__name__)
_THROTTLED_REFRESH = None


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the SABnzbd sensors."""
    from pysabnzbd import SabnzbdApi, SabnzbdApiException

    api_key = config.get("api_key")
    base_url = config.get("base_url")
    name = config.get("name", "SABnzbd")
    if not base_url:
        _LOGGER.error('Missing config variable base_url')
        return False
    if not api_key:
        _LOGGER.error('Missing config variable api_key')
        return False

    sab_api = SabnzbdApi(base_url, api_key)

    try:
        sab_api.check_available()
    except SabnzbdApiException:
        _LOGGER.exception("Connection to SABnzbd API failed.")
        return False

    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(timedelta(seconds=1))(sab_api.refresh_queue)

    dev = []
    for variable in config['monitored_variables']:
        if variable['type'] not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable['type'])
        else:
            dev.append(SabnzbdSensor(variable['type'], sab_api, name))

    add_devices(dev)


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
        return self.client_name + ' ' + self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def refresh_sabnzbd_data(self):
        """Call the throttled SABnzbd refresh method."""
        if _THROTTLED_REFRESH is not None:
            from pysabnzbd import SabnzbdApiException
            try:
                _THROTTLED_REFRESH()
            except SabnzbdApiException:
                _LOGGER.exception(
                    self.name + "  Connection to SABnzbd API failed."
                )

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
