"""Linky Atome."""
import logging
from datetime import timedelta

import voluptuous as vol
from pyatome.client import AtomeClient
from pyatome.client import PyAtomeError

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_NAME,
    DEVICE_CLASS_POWER,
    POWER_WATT,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"

SESSION_RENEW_INTERVAL = timedelta(minutes=55)

LIVE_SCAN_INTERVAL = timedelta(seconds=30)
DAILY_SCAN_INTERVAL = timedelta(seconds=150)
WEEKLY_SCAN_INTERVAL = timedelta(hours=1)
MONTHLY_SCAN_INTERVAL = timedelta(hours=1)
YEARLY_SCAN_INTERVAL = timedelta(days=1)

LIVE_NAME = "Atome Live Power"
DAILY_NAME = "Atome Daily"
WEEKLY_NAME = "Atome Weekly"
MONTHLY_NAME = "Atome Monthly"
YEARLY_NAME = "Atome Yearly"

LIVE_TYPE = "live"
DAILY_TYPE = "day"
WEEKLY_TYPE = "week"
MONTHLY_TYPE = "month"
YEARLY_TYPE = "year"

ICON = "mdi:flash"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Atome sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    data = AtomeData(username, password)

    @Throttle(LIVE_SCAN_INTERVAL)
    def update_live():
        """Update the live power usage."""
        data.get_live_power()

    @Throttle(DAILY_SCAN_INTERVAL)
    def update_daily():
        """Update the daily power usage."""
        data.get_daily_usage()

    @Throttle(WEEKLY_SCAN_INTERVAL)
    def update_weekly():
        """Update the weekly power usage."""
        data.get_weekly_usage()

    @Throttle(MONTHLY_SCAN_INTERVAL)
    def update_monthly():
        """Update the monthly power usage."""
        data.get_monthly_usage()

    @Throttle(YEARLY_SCAN_INTERVAL)
    def update_yearly():
        """Update the yearly power usage."""
        data.get_yearly_usage()

    update_live()
    update_daily()
    update_weekly()
    update_monthly()
    update_yearly()

    add_entities([AtomeSensor(data, LIVE_NAME, LIVE_TYPE, update_live)], True)
    add_entities([AtomeSensor(data, DAILY_NAME, DAILY_TYPE, update_daily)], True)
    add_entities([AtomeSensor(data, WEEKLY_NAME, WEEKLY_TYPE, update_weekly)], True)
    add_entities([AtomeSensor(data, MONTHLY_NAME, MONTHLY_TYPE, update_monthly)], True)
    add_entities([AtomeSensor(data, YEARLY_NAME, YEARLY_TYPE, update_yearly)], True)


class AtomeData:
    """Stores data retrieved from Neurio sensor."""

    def __init__(self, username, password):
        """Initialize the data."""
        self.username = username
        self.password = password
        self._live_power = None
        self._subscribed_power = None
        self._is_connected = None
        self._daily_usage = None
        self._daily_price = None
        self._weekly_usage = None
        self._weekly_price = None
        self._monthly_usage = None
        self._monthly_price = None
        self._yearly_usage = None
        self._yearly_price = None

        self._state = None

        try:
            self.atome_client = AtomeClient(username, password)
            self.atome_client.login()
        except PyAtomeError as exp:
            _LOGGER.error(exp)
            return

    @property
    def live_power(self):
        """Return latest active power value."""
        return self._live_power

    @property
    def subscribed_power(self):
        """Return latest active power value."""
        return self._subscribed_power

    @property
    def is_connected(self):
        """Return latest active power value."""
        return self._is_connected

    def get_live_power(self):
        """Return current power value."""
        try:
            values = self.atome_client.get_live()
            self._live_power = values["last"]
            self._subscribed_power = values["subscribed"]
            self._is_connected = values["isConnected"]
            _LOGGER.debug(
                "Updating Atome live data. Got: %d, isConnected: %s, subscribed: %d",
                self._live_power,
                self._is_connected,
                self._subscribed_power,
            )

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
            return None

    @property
    def daily_usage(self):
        """Return latest daily usage value."""
        return self._daily_usage

    @property
    def daily_price(self):
        """Return latest daily usage value."""
        return self._daily_price

    def get_daily_usage(self):
        """Return current daily power usage."""
        try:
            values = self.atome_client.get_consumption(DAILY_TYPE)
            self._daily_usage = values["total"] / 1000
            self._daily_price = values["price"]
            _LOGGER.debug("Updating Atome daily data. Got: %d.", self._daily_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
            return None

    @property
    def weekly_usage(self):
        """Return latest weekly usage value."""
        return self._weekly_usage

    @property
    def weekly_price(self):
        """Return latest weekly usage value."""
        return self._weekly_price

    def get_weekly_usage(self):
        """Return current weekly power usage."""
        try:
            values = self.atome_client.get_consumption(WEEKLY_TYPE)
            self._weekly_usage = values["total"] / 1000
            self._weekly_price = values["price"]
            _LOGGER.debug("Updating Atome weekly data. Got: %d.", self._weekly_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
            return None

    @property
    def monthly_usage(self):
        """Return latest monthly usage value."""
        return self._monthly_usage

    @property
    def monthly_price(self):
        """Return latest monthly usage value."""
        return self._monthly_price

    def get_monthly_usage(self):
        """Return current monthly power usage."""
        try:
            values = self.atome_client.get_consumption(MONTHLY_TYPE)
            self._monthly_usage = values["total"] / 1000
            self._monthly_price = values["price"]
            _LOGGER.debug("Updating Atome monthly data. Got: %d.", self._monthly_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
            return None

    @property
    def yearly_usage(self):
        """Return latest yearly usage value."""
        return self._yearly_usage

    @property
    def yearly_price(self):
        """Return latest yearly usage value."""
        return self._yearly_price

    def get_yearly_usage(self):
        """Return current yearly power usage."""
        try:
            values = self.atome_client.get_consumption(YEARLY_TYPE)
            self._yearly_usage = values["total"] / 1000
            self._yearly_price = values["price"]
            _LOGGER.debug("Updating Atome yearly data. Got: %d.", self._yearly_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
            return None


class AtomeSensor(Entity):
    """Representation of a sensor entity for Atome."""

    def __init__(self, data, name, sensor_type, update_call):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._state = None
        self._attributes = {}

        self._sensor_type = sensor_type
        self.update_sensor = update_call

        if sensor_type == LIVE_TYPE:
            self._unit_of_measurement = POWER_WATT
        else:
            self._unit_of_measurement = ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DEFAULT_NAME

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_POWER

    def update(self):
        """Update device state."""
        self.update_sensor()

        if self._sensor_type == LIVE_TYPE:
            self._state = self._data.live_power
            self._attributes["subscribed_power"] = self._data.subscribed_power
            self._attributes["is_connected"] = self._data.is_connected
        elif self._sensor_type == DAILY_TYPE:
            self._state = self._data.daily_usage
            self._attributes["price"] = self._data.daily_price
        elif self._sensor_type == WEEKLY_TYPE:
            self._state = self._data.weekly_usage
            self._attributes["price"] = self._data.daily_price
        elif self._sensor_type == MONTHLY_TYPE:
            self._state = self._data.monthly_usage
            self._attributes["price"] = self._data.daily_price
        elif self._sensor_type == YEARLY_TYPE:
            self._state = self._data.yearly_usage
            self._attributes["price"] = self._data.daily_price
