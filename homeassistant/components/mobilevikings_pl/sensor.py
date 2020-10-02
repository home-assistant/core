"""
Support for Mobile Vikings (in Poland).

Get data from "My account" page:
https://mobilevikings.pl/en/mysims
"""
import datetime
from datetime import timedelta
import logging

import mobilevikings_scraper
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DATA_GIGABYTES,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Mobile Vikings"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=30)

SENSOR_TYPES = {
    "balance": ["Balance", "PLN", "mdi:cash-usd"],
    "data_available": ["Data available", DATA_GIGABYTES, "mdi:download"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_MONITORED_VARIABLES): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    name = config.get(CONF_NAME)

    viking_data = VikingData(username, password)
    entities = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        entities.append(VikingSensor(viking_data, variable, name))
    add_entities(entities)


class VikingSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, viking_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._state = None
        self.viking_data = viking_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.client_name} {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {"number": self.viking_data.number}

    def update(self):
        """Fetch new state data for the sensor."""
        self.viking_data.update()
        if self.type == "balance":
            self._state = self.viking_data.balance
        elif self.type == "data_available":
            self._state = self.viking_data.data_available


class VikingData:
    """Data class containing all scraped data."""

    def __init__(self, username, password):
        """Init VikingData."""
        self._username = username
        self._password = password
        self._raw_data = None
        # Number
        self.number = None
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

    def _parse_data_str(self, data_str):
        """Parse string with data available."""
        x = data_str.lower().split(" ")
        x[0] = float(x[0])
        if x[1] == "gb":
            return x[0]
        elif x[1] == "mb":
            return x[0] / 1024
        elif x[1] == "kb":
            return x[0] / 1024 / 1024
        else:
            raise Exception("Error while parsing available data!")

    @Throttle(timedelta(seconds=15))  # TODO: Change that to default
    def update(self):
        """Fetch data from site."""
        try:
            data = mobilevikings_scraper.scrape(self._username, self._password)
            self._raw_data = data
            self.number = data["subscription"]["msisdn"]
            self.balance = float(data["balance"]["credit"])
            self.balance_type = data["balance"]["credit_type"]
            self.balance_expiration = datetime.datetime.strptime(
                data["balance"]["expiration_date"], "%d-%m-%Y"
            ).date()
            self.balance_expired = data["balance"]["is_expired"]

            self.data_is_available = data["services"][0]["available"]
            self.data_days_left = data["services"][0]["days_left"]
            self.data_scale_full = data["services"][0]["scale_full"]
            self.data_available = self._parse_data_str(
                data["services"][0]["pointer_description"]
            )
            self.data_expiration_date = datetime.datetime.strptime(
                data["services"][0]["expiration_date_text"], "%d-%m-%Y"
            ).date()
        except Exception as e:
            _LOGGER.error("Error on receive last MobileVikings data: %", e)
