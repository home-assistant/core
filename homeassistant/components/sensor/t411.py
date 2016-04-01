"""
Support for T411 torrent tracker.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.t411/
"""
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME)
from homeassistant.helpers import validate_config
from homeassistant.components.sensor import DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from datetime import timedelta
import logging

REQUIREMENTS = ['T411API==0.1.5', 'humanize==0.5.1']

_LOGGER = logging.getLogger(__name__)

# Return cached results if last scan was less then this time ago
# Data needed is not very flutuates very quickly so
# updating more than once per hour seems useless
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the T411 sensors."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_USERNAME,
                                     CONF_PASSWORD]},
                           _LOGGER):
        return False

    import t411api
    api = t411api.T411API()
    try:
        api.connect(config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None))
    except t411api.API.APIError as inst:
        _LOGGER.error(inst.args)
        return False

    add_devices([
        T411Sensor('username', api, config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None)),
        T411Sensor('uploaded', api, config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None)),
        T411Sensor('downloaded', api, config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None)),
        T411Sensor('ratio', api, config.get(CONF_USERNAME, None), config.get(CONF_PASSWORD, None))
    ])


class T411Sensor(Entity):
    """Representation of a T411 sensor."""

    def __init__(self, name, t411_data, username, password):
        """Initialize the sensor."""
        self._name = name
        self._t411 = t411_data
        self._username = username
        self._password = password

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format('T411', self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        import humanize
        import math
        if (self._name == 'username'):
            return self._t411.user()['username']
        elif (self._name == 'downloaded'):
            down = float(self._t411.user()['downloaded'])
            return humanize.naturalsize(down).split()[0]
        elif (self._name == 'uploaded'):
            up = float(self._t411.user()['uploaded'])
            return humanize.naturalsize(up).split()[0]
        elif (self._name == 'ratio'):
            down = float(self._t411.user()['downloaded'])
            up = float(self._t411.user()['uploaded'])
            ratio = math.floor(((up / down) * 100)) / 100
            return ratio
        else:
            return None

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if (self._name == 'username'):
            return 'mdi:account'
        elif (self._name == 'downloaded'):
            return 'mdi:download'
        elif (self._name == 'uploaded'):
            return 'mdi:upload'
        elif (self._name == 'ratio'):
            return 'mdi:percent'
        else:
            return None

    @property
    def unit_of_measurement(self):
        import humanize
        """Return the unit this state is expressed in."""
        if (self._name == 'downloaded'):
            down = float(self._t411.user()['downloaded'])
            return humanize.naturalsize(down).split()[1]
        elif (self._name == 'uploaded'):
            up = float(self._t411.user()['uploaded'])
            return humanize.naturalsize(up).split()[1]
        else:
            return None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Call the T411 API to update the data."""
        import t411api
        try:
            self._t411.connect(self._username, self._password)
        except t411api.API.APIError as inst:
            _LOGGER.error(inst.args)
            return False
