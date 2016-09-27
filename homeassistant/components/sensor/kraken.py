"""
Support for unleashing the Kraken.

This platform is for stress testing only.
"""
import logging
import re
import subprocess

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.bootstrap as bootstrap


_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional('tentacles', default=1): cv.positive_int,
    vol.Optional('templates', default=True): cv.boolean,
})

SCAN_INTERVAL = 1


def setup_platform(hass, config, add_devices, discovery_info=None): \
        # pylint: disable=unused-variable
    """Setup the KRAKEN."""
    sen = {}

    devs = []
    for idx in range(config['tentacles']):
        nme = 'kraken_{}'.format(idx)
        devs.append(KrakenSensor(nme))

        sen['kraken__{}'.format(idx)] = {
            'value_template': '{{ float(states.sensor.kraken_' + str(idx) +
                              '.state) + float(' + str(idx) + ') }}'}

    add_devices(devs)
    
    if config.get('templates'):

        platform = bootstrap.loader.get_platform('sensor', 'template')

        conf = {'platform': 'template', 'sensors': sen}
        conf = platform.PLATFORM_SCHEMA(conf)

        platform.setup_platform(hass, conf, add_devices)


def _seconds():
    """Get date, based on arp from nmap."""
    cmd = ['date', '+%H:%M:%S']
    arp = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, _ = arp.communicate()
    match = re.search(r'\d{2}:\d{2}:(\d{2})', str(out))
    if match:
        return match.group(1)
    return 0


class KrakenSensor(Entity):
    """Representation of a Kraken Tentacle."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._unit_of_measurement = 's'
        self.update()

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
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'About': 'The KRAKEN, handle with care.'}

    def update(self):
        """Get the latest data and updates the state."""
        self._state = _seconds()
        _LOGGER.debug('%s %s', self._name, self.state)
