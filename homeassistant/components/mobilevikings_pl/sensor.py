"""
Support for Mobile Vikings (in Poland).

Get data from "My account" page:
https://mobilevikings.pl/en/mysims
"""
from datetime import timedelta
import logging

import mobilevikings_scraper

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, DATA_GIGABYTES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    add_entities([VikingSensor(VikingData(username, password))])


class VikingSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, viking_data):
        """Initialize the sensor."""
        self._icon = "mdi:cellphone"
        self._number = "666999666"
        self._state = None
        self.viking_data = viking_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Mobile Vikings"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return DATA_GIGABYTES

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"number": self._number}

    def update(self):
        """Fetch new state data for the sensor."""
        self.viking_data.update()
        self._state = self.viking_data.data_available


class VikingData:
    """Data class containing all scraped data."""

    def __init__(self, username, password):
        """Init VikingData."""
        self._username = username
        self._password = password
        self._raw_data = None
        # Balance
        self.balance = None
        self.balance_type = None
        self.balance_expiration = None
        self.balance_expired = None
        # Data
        self.data_is_available = None
        self.data_days_left = None
        self.data_scale_full = None
        self.data_available = None
        self.data_expiration_date = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch data from site."""
        try:
            data = mobilevikings_scraper.scrape(self._username, self._password)
            self._raw_data = data
            self.balance = data["balance"]["credit"]
            self.balance_type = data["balance"]["credit_type"]
            self.balance_expiration = data["balance"][
                "expiration_date"
            ]  # TODO: Parse this
            self.balance_expired = data["balance"]["is_expired"]

            self.data_is_available = data["services"][0]["available"]
            self.data_days_left = data["services"][0]["days_left"]
            self.data_scale_full = data["services"][0]["scale_full"]
            self.data_available = data["services"][0]["pointer_description"].split(" ")[
                0
            ]  # TODO: Parse this
            self.data_expiration_date = data["services"][0][
                "expiration_date_text"
            ]  # TODO: Parse this
        except Exception as e:
            _LOGGER.error("Error on receive last MobileVikings data: %", e)
