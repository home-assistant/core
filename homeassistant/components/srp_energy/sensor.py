"""
Platform for retrieving energy data from SRP.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.srp_energy/
"""
from datetime import datetime, timedelta
import logging

from requests.exceptions import (
    ConnectionError as ConnectError, HTTPError, Timeout)
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_PASSWORD, ENERGY_KILO_WATT_HOUR,
    CONF_USERNAME, CONF_ID)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['srpenergy==1.0.6']

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Powered by SRP Energy"

DEFAULT_NAME = 'SRP Energy'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=1440)
ENERGY_KWH = ENERGY_KILO_WATT_HOUR

ATTR_READING_COST = "reading_cost"
ATTR_READING_TIME = 'datetime'
ATTR_READING_USAGE = 'reading_usage'
ATTR_DAILY_USAGE = 'daily_usage'
ATTR_USAGE_HISTORY = 'usage_history'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_ID): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SRP energy."""
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    account_id = config[CONF_ID]

    from srpenergy.client import SrpEnergyClient

    srp_client = SrpEnergyClient(account_id, username, password)

    if not srp_client.validate():
        _LOGGER.error("Couldn't connect to %s. Check credentials", name)
        return

    add_entities([SrpEnergy(name, srp_client)], True)


class SrpEnergy(Entity):
    """Representation of an srp usage."""

    def __init__(self, name, client):
        """Initialize SRP Usage."""
        self._state = None
        self._name = name
        self._client = client
        self._history = None
        self._usage = None

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def state(self):
        """Return the current state."""
        if self._state is None:
            return None

        return "{0:.2f}".format(self._state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return ENERGY_KWH

    @property
    def history(self):
        """Return the energy usage history of this entity, if any."""
        if self._usage is None:
            return None

        history = [{
            ATTR_READING_TIME: isodate,
            ATTR_READING_USAGE: kwh,
            ATTR_READING_COST: cost
            } for _, _, isodate, kwh, cost in self._usage]

        return history

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {
            ATTR_USAGE_HISTORY: self.history
        }

        return attributes

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest usage from SRP Energy."""
        start_date = datetime.now() + timedelta(days=-1)
        end_date = datetime.now()

        try:

            usage = self._client.usage(start_date, end_date)

            daily_usage = 0.0
            for _, _, _, kwh, _ in usage:
                daily_usage += float(kwh)

            if usage:

                self._state = daily_usage
                self._usage = usage

            else:
                _LOGGER.error("Unable to fetch data from SRP. No data")

        except (ConnectError, HTTPError, Timeout) as error:
            _LOGGER.error("Unable to connect to SRP. %s", error)
        except ValueError as error:
            _LOGGER.error("Value error connecting to SRP. %s", error)
        except TypeError as error:
            _LOGGER.error("Type error connecting to SRP. "
                          "Check username and password. %s", error)
