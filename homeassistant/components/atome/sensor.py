"""Linky Atome."""
from datetime import timedelta
import logging

from pyatome.client import AtomeClient, PyAtomeError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"

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

    try:
        atome_client = AtomeClient(username, password)
        atome_client.login()
    except PyAtomeError as exp:
        _LOGGER.error(exp)
        return

    data = AtomeData(atome_client)

    sensors = []
    sensors.append(AtomeSensor(data, LIVE_NAME, LIVE_TYPE))
    sensors.append(AtomeSensor(data, DAILY_NAME, DAILY_TYPE))
    sensors.append(AtomeSensor(data, WEEKLY_NAME, WEEKLY_TYPE))
    sensors.append(AtomeSensor(data, MONTHLY_NAME, MONTHLY_TYPE))
    sensors.append(AtomeSensor(data, YEARLY_NAME, YEARLY_TYPE))

    add_entities(sensors, True)


class AtomeData:
    """Stores data retrieved from Neurio sensor."""

    def __init__(self, client: AtomeClient) -> None:
        """Initialize the data."""
        self.atome_client = client
        self._live_power = None
        self._subscribed_power = None
        self._is_connected = None
        self._day_usage = None
        self._day_price = None
        self._week_usage = None
        self._week_price = None
        self._month_usage = None
        self._month_price = None
        self._year_usage = None
        self._year_price = None

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

    @Throttle(LIVE_SCAN_INTERVAL)
    def update_live_usage(self):
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

    @property
    def day_usage(self):
        """Return latest daily usage value."""
        return self._day_usage

    @property
    def day_price(self):
        """Return latest daily usage value."""
        return self._day_price

    @Throttle(DAILY_SCAN_INTERVAL)
    def update_day_usage(self):
        """Return current daily power usage."""
        try:
            values = self.atome_client.get_consumption(DAILY_TYPE)
            self._day_usage = values["total"] / 1000
            self._day_price = values["price"]
            _LOGGER.debug("Updating Atome daily data. Got: %d", self._day_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)

    @property
    def week_usage(self):
        """Return latest weekly usage value."""
        return self._week_usage

    @property
    def week_price(self):
        """Return latest weekly usage value."""
        return self._week_price

    @Throttle(WEEKLY_SCAN_INTERVAL)
    def update_week_usage(self):
        """Return current weekly power usage."""
        try:
            values = self.atome_client.get_consumption(WEEKLY_TYPE)
            self._week_usage = values["total"] / 1000
            self._week_price = values["price"]
            _LOGGER.debug("Updating Atome weekly data. Got: %d", self._week_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)

    @property
    def month_usage(self):
        """Return latest monthly usage value."""
        return self._month_usage

    @property
    def month_price(self):
        """Return latest monthly usage value."""
        return self._month_price

    @Throttle(MONTHLY_SCAN_INTERVAL)
    def update_month_usage(self):
        """Return current monthly power usage."""
        try:
            values = self.atome_client.get_consumption(MONTHLY_TYPE)
            self._month_usage = values["total"] / 1000
            self._month_price = values["price"]
            _LOGGER.debug("Updating Atome monthly data. Got: %d", self._month_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)

    @property
    def year_usage(self):
        """Return latest yearly usage value."""
        return self._year_usage

    @property
    def year_price(self):
        """Return latest yearly usage value."""
        return self._year_price

    @Throttle(YEARLY_SCAN_INTERVAL)
    def update_year_usage(self):
        """Return current yearly power usage."""
        try:
            values = self.atome_client.get_consumption(YEARLY_TYPE)
            self._year_usage = values["total"] / 1000
            self._year_price = values["price"]
            _LOGGER.debug("Updating Atome yearly data. Got: %d", self._year_usage)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)


class AtomeSensor(SensorEntity):
    """Representation of a sensor entity for Atome."""

    _attr_device_class = DEVICE_CLASS_POWER

    def __init__(self, data, name, sensor_type):
        """Initialize the sensor."""
        self._attr_name = name
        self._data = data

        self._sensor_type = sensor_type

        if sensor_type == LIVE_TYPE:
            self._attr_unit_of_measurement = POWER_WATT
            self._attr_state_class = STATE_CLASS_MEASUREMENT
        else:
            self._attr_unit_of_measurement = ENERGY_KILO_WATT_HOUR

    def update(self):
        """Update device state."""
        update_function = getattr(self._data, f"update_{self._sensor_type}_usage")
        update_function()

        if self._sensor_type == LIVE_TYPE:
            self._attr_state = self._data.live_power
            self._attr_extra_state_attributes = {
                "subscribed_power": self._data.subscribed_power,
                "is_connected": self._data.is_connected,
            }
        else:
            self._attr_state = getattr(self._data, f"{self._sensor_type}_usage")
            self._attr_extra_state_attributes = {
                "price": getattr(self._data, f"{self._sensor_type}_price")
            }
