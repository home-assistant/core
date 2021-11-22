"""Linky Atome."""
from datetime import timedelta
import logging

from pyatome.client import AtomeClient, PyAtomeError
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"

ATTRIBUTION = "Data provided by TotalEnergies"

ATTR_PREVIOUS_PERIOD_USAGE = "previous_consumption"
ATTR_PREVIOUS_PERIOD_PRICE = "previous_price"
ATTR_PERIOD_PRICE = "price"

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

    sensors = [
        AtomeLiveSensor(hass, atome_client),
        AtomeDailySensor(hass, atome_client),
        AtomeWeeklySensor(hass, atome_client),
        AtomeMonthlySensor(hass, atome_client),
        AtomeYearlySensor(hass, atome_client),
    ]

    add_entities(sensors, True)


class AtomeGenericSensor(SensorEntity):
    """Basic class to store atome client."""

    def __init__(self, hass, atome_client, name, period_type):
        """Initialize the data."""
        self._atome_client = atome_client
        self._name = name
        self._period_type = period_type
        self._hass = hass

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


class AtomeLiveSensor(AtomeGenericSensor):
    """Class used to retrieve Live Data."""

    def __init__(self, hass, atome_client):
        """Initialize the data."""
        super().__init__(hass, atome_client, LIVE_NAME, LIVE_TYPE)
        self._live_power = None
        self._subscribed_power = None
        self._is_connected = None

        self._attr_device_class = DEVICE_CLASS_POWER
        self._attr_native_unit_of_measurement = POWER_WATT
        self._attr_state_class = STATE_CLASS_MEASUREMENT

    def _retrieve_live(self):
        """Retrieve Live data."""
        values = self._atome_client.get_live()
        if (
            values.get("last")
            and values.get("subscribed")
            and (values.get("isConnected") is not None)
        ):
            self._live_power = values["last"]
            self._subscribed_power = values["subscribed"]
            self._is_connected = values["isConnected"]
            _LOGGER.debug(
                "Updating Atome live data. Got: %d, isConnected: %s, subscribed: %d",
                self._live_power,
                self._is_connected,
                self._subscribed_power,
            )
            return True

        _LOGGER.error("Live Data : Missing last value in values: %s", values)
        return False

    @Throttle(LIVE_SCAN_INTERVAL)
    def update_live_usage(self):
        """Return current power value."""
        _LOGGER.debug("Live Data : Update Usage")
        if not self._retrieve_live():
            _LOGGER.debug("Perform Reconnect during live request")
            self._atome_client.login()
            self._retrieve_live()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        attr["subscribed_power"] = self._subscribed_power
        attr["is_connected"] = self._is_connected
        return attr

    @property
    def state(self):
        """Return the state of this device."""
        _LOGGER.debug("Live Data : display")
        return self._live_power

    async def async_update(self):
        """Fetch new state data for this sensor."""
        _LOGGER.debug("Async Update sensor %s", self._name)
        # Watch Out : only method name is given to function i.e. without ()
        await self._hass.async_add_executor_job(self.update_live_usage)


class AtomePeriodSensor(RestoreEntity, AtomeGenericSensor):
    """Class used to retrieve Period Data."""

    def __init__(self, hass, atome_client, name, period_type):
        """Initialize the data."""
        super().__init__(hass, atome_client, name, period_type)
        self._period_usage = None
        self._period_price = None
        self._previous_period_usage = None
        self._previous_period_price = None

        self._attr_device_class = DEVICE_CLASS_ENERGY
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
        self._attr_state_class = STATE_CLASS_TOTAL_INCREASING

    async def async_added_to_hass(self):
        """Handle added to Hass."""
        # restore from previous run
        await super().async_added_to_hass()
        state_recorded = await self.async_get_last_state()
        if state_recorded:
            self._period_usage = state_recorded.state
            self._period_price = state_recorded.attributes.get(
                ATTR_PERIOD_PRICE
            )
            self._previous_period_usage = state_recorded.attributes.get(
                ATTR_PREVIOUS_PERIOD_USAGE
            )
            self._previous_period_price = state_recorded.attributes.get(
                ATTR_PREVIOUS_PERIOD_PRICE
            )

    def _retrieve_period_usage(self):
        """Return current daily/weekly/monthly/yearly power usage."""
        values = self._atome_client.get_consumption(self._period_type)
        if values.get("total") and values.get("price"):
            if (self._period_usage is not None) and (
                (values["total"] / 1000) < self._period_usage
            ):
                self._previous_period_usage = self._period_usage
                self._previous_period_price = self._period_price
            self._period_usage = values["total"] / 1000
            self._period_price = values["price"]
            _LOGGER.debug(
                "Updating Atome %s data. Got: %d", self._period_type, self._period_usage
            )
            return True

        _LOGGER.error(
            "%s : Missing last value in values: %s", self._period_type, values
        )
        return False

    def _retrieve_period_usage_with_retry(self):
        """Return current daily/weekly/monthly/yearly power usage with one retry."""

        if not self._retrieve_period_usage():
            _LOGGER.debug("Perform Reconnect during %s", self._period_type)
            self._atome_client.login()
            self._retrieve_period_usage()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        attr[ATTR_PERIOD_PRICE] = self._period_price
        attr[ATTR_PREVIOUS_PERIOD_USAGE] = self._previous_period_usage
        attr[ATTR_PREVIOUS_PERIOD_PRICE] = self._previous_period_price
        return attr

    @property
    def state(self):
        """Return the state of this device."""
        return self._period_usage

    def update_period_usage(self):
        """Return current daily power usage."""
        # This function can be instantiated
        self._retrieve_period_usage_with_retry()

    async def async_update(self):
        """Fetch new state data for this sensor."""
        _LOGGER.debug("Async Update sensor %s", self._name)
        # Watch Out : only method name is given to function i.e. without ()
        await self._hass.async_add_executor_job(self.update_period_usage)


class AtomeDailySensor(AtomePeriodSensor):
    """Class used to retrieve Daily Data."""

    def __init__(self, hass, atome_client):
        """Initialize the data."""
        super().__init__(hass, atome_client, DAILY_NAME, DAILY_TYPE)

    @Throttle(DAILY_SCAN_INTERVAL)
    def update_period_usage(self):
        """Return current daily power usage."""
        self._retrieve_period_usage_with_retry()


class AtomeWeeklySensor(AtomePeriodSensor):
    """Class used to retrieve Weekly Data."""

    def __init__(self, hass, atome_client):
        """Initialize the data."""
        super().__init__(hass, atome_client, WEEKLY_NAME, WEEKLY_TYPE)

    @Throttle(WEEKLY_SCAN_INTERVAL)
    def update_period_usage(self):
        """Return current daily power usage."""
        self._retrieve_period_usage_with_retry()


class AtomeMonthlySensor(AtomePeriodSensor):
    """Class used to retrieve Monthly Data."""

    def __init__(self, hass, atome_client):
        """Initialize the data."""
        super().__init__(hass, atome_client, MONTHLY_NAME, MONTHLY_TYPE)

    @Throttle(MONTHLY_SCAN_INTERVAL)
    def update_period_usage(self):
        """Return current daily power usage."""
        self._retrieve_period_usage_with_retry()


class AtomeYearlySensor(AtomePeriodSensor):
    """Class used to retrieve Yearly Data."""

    def __init__(self, hass, atome_client):
        """Initialize the data."""
        super().__init__(hass, atome_client, YEARLY_NAME, YEARLY_TYPE)

    @Throttle(YEARLY_SCAN_INTERVAL)
    def update_period_usage(self):
        """Return current daily power usage."""
        self._retrieve_period_usage_with_retry()
