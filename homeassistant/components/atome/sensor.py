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
    STATE_UNKNOWN,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"

DOMAIN = "atome"

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


def format_receive_value(value):
    """Format if pb then return None."""
    if value is None or value == STATE_UNKNOWN:
        return None
    return float(value)


async def async_create_period_coordinator(
    hass, atome_client, name, sensor_type, scan_interval
):
    """Create coordinator for period data."""
    atome_period_end_point = AtomePeriodServerEndPoint(atome_client, name, sensor_type)

    async def async_period_update_data():
        data = await hass.async_add_executor_job(atome_period_end_point.retrieve_data)
        return data

    period_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_period_update_data,
        update_interval=scan_interval,
    )
    await period_coordinator.async_refresh()
    return period_coordinator


async def async_create_live_coordinator(hass, atome_client):
    """Create coordinator for live data."""
    atome_live_end_point = AtomeLiveServerEndPoint(atome_client)

    async def async_live_update_data():
        data = await hass.async_add_executor_job(atome_live_end_point.retrieve_data)
        return data

    live_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_live_update_data,
        update_interval=LIVE_SCAN_INTERVAL,
    )
    await live_coordinator.async_refresh()
    return live_coordinator


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Atome sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        atome_client = AtomeClient(username, password)
        await hass.async_add_executor_job(atome_client.login)
    except PyAtomeError as exp:
        _LOGGER.error(exp)
        return

    # Live Data
    live_coordinator = await async_create_live_coordinator(hass, atome_client)

    # Periodic Data
    daily_coordinator = await async_create_period_coordinator(
        hass, atome_client, DAILY_NAME, DAILY_TYPE, DAILY_SCAN_INTERVAL
    )
    weekly_coordinator = await async_create_period_coordinator(
        hass, atome_client, WEEKLY_NAME, WEEKLY_TYPE, WEEKLY_SCAN_INTERVAL
    )
    monthly_coordinator = await async_create_period_coordinator(
        hass, atome_client, MONTHLY_NAME, MONTHLY_TYPE, MONTHLY_SCAN_INTERVAL
    )
    yearly_coordinator = await async_create_period_coordinator(
        hass, atome_client, YEARLY_NAME, YEARLY_TYPE, YEARLY_SCAN_INTERVAL
    )

    sensors = [
        AtomeLiveSensor(live_coordinator),
        AtomePeriodSensor(daily_coordinator, DAILY_NAME, DAILY_TYPE),
        AtomePeriodSensor(weekly_coordinator, WEEKLY_NAME, WEEKLY_TYPE),
        AtomePeriodSensor(monthly_coordinator, MONTHLY_NAME, MONTHLY_TYPE),
        AtomePeriodSensor(yearly_coordinator, YEARLY_NAME, YEARLY_TYPE),
    ]

    async_add_entities(sensors, True)


class AtomeGenericServerEndPoint:
    """Basic class to retrieve data from server."""

    def __init__(self, atome_client, name, period_type):
        """Initialize the data."""
        self._atome_client = atome_client
        self._name = name
        self._period_type = period_type


class AtomeLiveData:
    """Class used to store Live Data."""

    def __init__(self):
        """Initialize the data."""
        self.live_power = None
        self.subscribed_power = None
        self.is_connected = None


class AtomeLiveServerEndPoint(AtomeGenericServerEndPoint):
    """Class used to retrieve Live Data."""

    def __init__(self, atome_client):
        """Initialize the data."""
        super().__init__(atome_client, LIVE_NAME, LIVE_TYPE)
        self._live_data = AtomeLiveData()

    def _retrieve_live(self):
        """Retrieve Live data."""
        values = self._atome_client.get_live()
        if (
            values.get("last")
            and values.get("subscribed")
            and (values.get("isConnected") is not None)
        ):
            self._live_data.live_power = values["last"]
            self._live_data.subscribed_power = values["subscribed"]
            self._live_data.is_connected = values["isConnected"]
            _LOGGER.debug(
                "Updating Atome live data. Got: %d, isConnected: %s, subscribed: %d",
                self._live_data.live_power,
                self._live_data.is_connected,
                self._live_data.subscribed_power,
            )
            return True

        _LOGGER.error("Live Data : Missing last value in values: %s", values)
        return False

    def retrieve_data(self):
        """Return current power value."""
        _LOGGER.debug("Live Data : Update Usage")
        self._live_data = AtomeLiveData()
        if not self._retrieve_live():
            _LOGGER.debug("Perform Reconnect during live request")
            self._atome_client.login()
            self._retrieve_live()
        return self._live_data


class AtomePeriodData:
    """Class used to store period Data."""

    def __init__(self):
        """Initialize the data."""
        self.usage = None
        self.price = None


class AtomePeriodServerEndPoint(AtomeGenericServerEndPoint):
    """Class used to retrieve Period Data."""

    def __init__(self, atome_client, name, period_type):
        """Initialize the data."""
        super().__init__(atome_client, name, period_type)
        self._period_data = AtomePeriodData()

    def _retrieve_period_usage(self):
        """Return current daily/weekly/monthly/yearly power usage."""
        values = self._atome_client.get_consumption(self._period_type)
        if values.get("total") and values.get("price"):
            self._period_data.usage = values["total"] / 1000
            self._period_data.price = values["price"]
            _LOGGER.debug(
                "Updating Atome %s data. Got: %d",
                self._period_type,
                self._period_data.usage,
            )
            return True

        _LOGGER.error(
            "%s : Missing last value in values: %s", self._period_type, values
        )
        return False

    def retrieve_data(self):
        """Return current daily/weekly/monthly/yearly power usage with one retry."""
        self._period_data = AtomePeriodData()
        if not self._retrieve_period_usage():
            _LOGGER.debug("Perform Reconnect during %s", self._period_type)
            self._atome_client.login()
            self._retrieve_period_usage()
        return self._period_data


class AtomeGenericSensor(CoordinatorEntity, SensorEntity):
    """Basic class to store atome client."""

    def __init__(self, coordinator, name, period_type):
        """Initialize the data."""
        super().__init__(coordinator)
        self._name = name
        self._period_type = period_type

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.update_from_latest_data()
            self.async_write_ha_state()

        self.async_on_remove(self.coordinator.async_add_listener(update))

        self.update_from_latest_data()

    @callback
    def update_from_latest_data(self) -> None:
        """Update the entity from the latest data."""
        raise NotImplementedError

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name


class AtomeLiveSensor(AtomeGenericSensor):
    """Class used to retrieve Live Data."""

    def __init__(self, coordinator):
        """Initialize the data."""
        super().__init__(coordinator, LIVE_NAME, LIVE_TYPE)
        self._live_data = None

        # HA attributes
        self._attr_device_class = DEVICE_CLASS_POWER
        self._attr_native_unit_of_measurement = POWER_WATT
        self._attr_state_class = STATE_CLASS_MEASUREMENT

    @property
    def extra_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        attr["subscribed_power"] = self._live_data.subscribed_power
        attr["is_connected"] = self._live_data.is_connected
        return attr

    @property
    def native_value(self):
        """Return the state of this device."""
        _LOGGER.debug("Live Data : display")
        return self._live_data.live_power

    def update_from_latest_data(self):
        """Fetch new state data for this sensor."""
        _LOGGER.debug("Async Update sensor %s", self._name)
        self._live_data = self.coordinator.data


class AtomePeriodSensor(RestoreEntity, AtomeGenericSensor):
    """Class used to retrieve Period Data."""

    def __init__(self, coordinator, name, period_type):
        """Initialize the data."""
        super().__init__(coordinator, name, period_type)
        self._period_data = AtomePeriodData()
        self._previous_period_data = AtomePeriodData()

        # HA attributes
        self._attr_device_class = DEVICE_CLASS_ENERGY
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
        self._attr_state_class = STATE_CLASS_TOTAL_INCREASING

    async def async_added_to_hass(self):
        """Handle added to Hass."""
        # restore from previous run
        state_recorded = await self.async_get_last_state()
        if state_recorded:
            self._period_data.usage = format_receive_value(state_recorded.state)
            self._period_data.price = format_receive_value(
                state_recorded.attributes.get(ATTR_PERIOD_PRICE)
            )
            self._previous_period_data.usage = format_receive_value(
                state_recorded.attributes.get(ATTR_PREVIOUS_PERIOD_USAGE)
            )
            self._previous_period_data.price = format_receive_value(
                state_recorded.attributes.get(ATTR_PREVIOUS_PERIOD_PRICE)
            )
        await super().async_added_to_hass()

    @property
    def extra_state_attributes(self):
        """Return the state attributes of this device."""
        attr = {ATTR_ATTRIBUTION: ATTRIBUTION}
        attr[ATTR_PERIOD_PRICE] = self._period_data.price
        attr[ATTR_PREVIOUS_PERIOD_USAGE] = self._previous_period_data.usage
        attr[ATTR_PREVIOUS_PERIOD_PRICE] = self._previous_period_data.price
        return attr

    @property
    def native_value(self):
        """Return the state of this device."""
        return self._period_data.usage

    def update_from_latest_data(self):
        """Fetch new state data for this sensor."""
        _LOGGER.debug("Async Update sensor %s", self._name)
        new_period_data = self.coordinator.data
        if new_period_data.usage and self._period_data.usage:
            _LOGGER.debug(
                "Check period %s : New %s ; Current %s",
                self._name,
                new_period_data.usage,
                self._period_data.usage,
            )
            # Take a margin to avoid storage of previous data
            if (new_period_data.usage - self._period_data.usage) < (-1.0):
                _LOGGER.debug(
                    "Previous period %s becomes %s", self._name, self._period_data.usage
                )
                self._previous_period_data = self._period_data
        self._period_data = new_period_data
