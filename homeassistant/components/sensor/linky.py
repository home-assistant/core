"""
Support for Linky.
For more details about this component, please refer to the documentation at
https://home-assistant.io/components/sensor.linky/
"""
import logging
import json
from datetime import timedelta
import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pylinky==0.1.5']
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'linky'

TIME_BETWEEN_UPDATES = timedelta(days=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Configure the platform and add the Linky sensor."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    from pylinky.client import LinkyClient
    client = LinkyClient(username, password)

    # get the last past day data
    devices = [LinkySensor('Linky', client)]
    add_devices(devices, True)


class LinkySensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, name, client):
        self._name = name
        self._client = client
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        self.update()
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'kWh'

    @Throttle(TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self._client.fetch_data()
        except BaseException as exp:
            _LOGGER.error(exp)
        finally:
            self._client.close_session()

        _LOGGER.debug(json.dumps(self._client.get_data(), indent=2))

        if self._client.get_data():
            self._state = self._client.get_data().get('daily')[-2].get('conso')
        else:
            self._state = 0
