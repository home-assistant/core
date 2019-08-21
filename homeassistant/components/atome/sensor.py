"""Linky Atome."""
import logging
from datetime import timedelta
from pyatome import AtomeClient
import voluptuous as vol


from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, CONF_NAME
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"
DEFAULT_UNIT = "W"
DEFAULT_CLASS = "power"

SCAN_INTERVAL = timedelta(seconds=30)
SESSION_RENEW_INTERVAL = timedelta(minutes=55)
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    """Initiate Atome Client object"""
    try:
        client = AtomeClient(username, password)
    except PyAtomeError as exp:
        _LOGGER.error(exp)
    except Exception as exp:
        _LOGGER.error(exp)
    # finally:
    #     client.close_session()

    add_entities(
        [
            AtomeSensor(
                name,
                client
            )
        ]
    )
    return True

class AtomeSensor(Entity):
    """Representation of a sensor entity for Atome."""

    def __init__(self,name,client: AtomeClient):

        """Initialize the sensor."""
        _LOGGER.debug("ATOME: INIT : %s",str(client))
        self._name = name
        # self._unit = DEFAULT_UNIT
        self._unit_of_measurement = DEFAULT_UNIT
        self._device_class = DEFAULT_CLASS

        self._client = client


        self._attributes = None
        self._state = None
        self._login()
        self.get_live()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DEFAULT_NAME

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    # @Throttle(SESSION_RENEW_INTERVAL)
    def _login(self):

        return self._client.login()

    def _get_data(self):

        return self._client.get_live()


    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update device state."""
        _LOGGER.debug("ATOME: Starting update of Atome Data")

        values = self._get_data()
        self._state = values["last"]
