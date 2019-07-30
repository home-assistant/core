"""Support for Linky."""
import json
import logging
from datetime import timedelta

import voluptuous as vol
from pylinky.client import DAILY, MONTHLY, YEARLY, LinkyClient, PyLinkyError

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=4)
ICON_ENERGY = "mdi:flash"
CONSUMPTION = "conso"
TIME = "time"
INDEX_CURRENT = -1
INDEX_LAST = -2
ATTRIBUTION = "Data provided by Enedis"

SENSORS = {
    "yesterday": ("Linky yesterday", DAILY, INDEX_LAST),
    "current_month": ("Linky current month", MONTHLY, INDEX_CURRENT),
    "last_month": ("Linky last month", MONTHLY, INDEX_LAST),
    "current_year": ("Linky current year", YEARLY, INDEX_CURRENT),
    "last_year": ("Linky last year", YEARLY, INDEX_LAST),
}
SENSORS_INDEX_LABEL = 0
SENSORS_INDEX_SCALE = 1
SENSORS_INDEX_WHEN = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

_LOGGER.error("LINKY_SENSOR")


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Linky sensor from legacy config file."""
    _LOGGER.error("LINKY_SENSOR:setup_platform")
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Add Linky entries."""
    _LOGGER.error("LINKY_SENSOR:async_setup_entry")
    account = LinkyAccount(
        hass,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_TIMEOUT],
    )
    async_add_entities(account.sensors, True)


class LinkyAccount:
    """Representation of a Linky account."""

    def __init__(self, hass, username, password, timeout):
        """Initialise the Linky account."""

        _LOGGER.error("LINKY_SENSOR:account init")
        self._username = username
        self.__password = password
        self._timeout = timeout
        self._data = None
        self.sensors = []

        self.update_linky_data(dt_util.utcnow())

        self.sensors.append(LinkySensor("Linky yesterday", self, DAILY, INDEX_LAST))
        self.sensors.append(
            LinkySensor("Linky current month", self, MONTHLY, INDEX_CURRENT)
        )
        self.sensors.append(LinkySensor("Linky last month", self, MONTHLY, INDEX_LAST))
        self.sensors.append(
            LinkySensor("Linky current year", self, YEARLY, INDEX_CURRENT)
        )
        self.sensors.append(LinkySensor("Linky last year", self, YEARLY, INDEX_LAST))

        track_time_interval(hass, self.update_linky_data, SCAN_INTERVAL)

    def update_linky_data(self, event_time):
        """Fetch new state data for the sensor."""
        client = LinkyClient(self._username, self.__password, None, self._timeout)
        try:
            client.login()
            client.fetch_data()
            self._data = client.get_data()
            _LOGGER.debug(json.dumps(self._data, indent=2))
        except PyLinkyError as exp:
            _LOGGER.error(exp)
        finally:
            client.close_session()

        _LOGGER.error("LINKY_SENSOR:update finished")

    @property
    def username(self):
        """Return the username."""
        return self._username

    @property
    def data(self):
        """Return the data."""
        return self._data


class LinkySensor(Entity):
    """Representation of a sensor entity for Linky."""

    def __init__(self, name, account: LinkyAccount, scale, when):
        """Initialize the sensor."""
        _LOGGER.error("LINKY_SENSOR:sensor init : %s", name)
        self._name = name
        self.__account = account
        self._scale = scale
        self.__when = when
        self._username = account.username
        self.__time = None
        self.__consumption = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.__consumption

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return ICON_ENERGY

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            "time": self.__time,
            CONF_USERNAME: self._username,
        }

    def update(self):
        """Retrieve the new data for the sensor."""
        _LOGGER.error("LINKY_SENSOR:sensor update : %s", self.name)
        data = self.__account.data[self._scale][self.__when]
        self.__consumption = data[CONSUMPTION]
        self.__time = data[TIME]

        if self._scale is not YEARLY:
            year_index = INDEX_CURRENT
            if self.__time.endswith("Dec"):
                year_index = INDEX_LAST
            self.__time += " " + self.__account.data[YEARLY][year_index][TIME]
