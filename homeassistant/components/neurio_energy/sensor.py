"""Support for monitoring a Neurio energy sensor."""

from __future__ import annotations

from datetime import timedelta
import logging

import neurio
import requests.exceptions
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONF_API_KEY, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util

_LOGGER = logging.getLogger(__name__)

CONF_API_SECRET = "api_secret"
CONF_SENSOR_ID = "sensor_id"

ACTIVE_NAME = "Energy Usage"
DAILY_NAME = "Daily Energy Usage"

ACTIVE_TYPE = "active"
DAILY_TYPE = "daily"


MIN_TIME_BETWEEN_DAILY_UPDATES = timedelta(seconds=150)
MIN_TIME_BETWEEN_ACTIVE_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_API_SECRET): cv.string,
        vol.Required(CONF_SENSOR_ID): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Neurio sensor."""
    api_key = config.get(CONF_API_KEY)
    api_secret = config.get(CONF_API_SECRET)
    sensor_id = config.get(CONF_SENSOR_ID)

    data = NeurioData(api_key, api_secret, sensor_id)

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_daily():
        """Update the daily power usage."""
        data.get_daily_usage()

    @Throttle(MIN_TIME_BETWEEN_ACTIVE_UPDATES)
    def update_active():
        """Update the active power usage."""
        data.get_active_power()

    update_daily()
    update_active()

    # Active power sensor
    add_entities([NeurioEnergy(data, ACTIVE_NAME, ACTIVE_TYPE, update_active)])
    # Daily power sensor
    add_entities([NeurioEnergy(data, DAILY_NAME, DAILY_TYPE, update_daily)])


class NeurioData:
    """Stores data retrieved from Neurio sensor."""

    def __init__(self, api_key, api_secret, sensor_id):
        """Initialize the data."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.sensor_id = sensor_id

        self._daily_usage = None
        self._active_power = None

        self._state = None

        neurio_tp = neurio.TokenProvider(key=api_key, secret=api_secret)
        self.neurio_client = neurio.Client(token_provider=neurio_tp)

    @property
    def daily_usage(self):
        """Return latest daily usage value."""
        return self._daily_usage

    @property
    def active_power(self):
        """Return latest active power value."""
        return self._active_power

    def get_active_power(self) -> None:
        """Return current power value."""
        try:
            sample = self.neurio_client.get_samples_live_last(self.sensor_id)
            self._active_power = sample["consumptionPower"]
        except (requests.exceptions.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update current power usage")

    def get_daily_usage(self) -> None:
        """Return current daily power usage."""
        kwh = 0
        start_time = dt_util.start_of_local_day().astimezone(dt_util.UTC).isoformat()
        end_time = dt_util.utcnow().isoformat()

        _LOGGER.debug("Start: %s, End: %s", start_time, end_time)

        try:
            history = self.neurio_client.get_samples_stats(
                self.sensor_id, start_time, "days", end_time
            )
        except (requests.exceptions.RequestException, ValueError, KeyError):
            _LOGGER.warning("Could not update daily power usage")
            return

        for result in history:
            kwh += result["consumptionEnergy"] / 3600000

        self._daily_usage = round(kwh, 2)


class NeurioEnergy(SensorEntity):
    """Implementation of a Neurio energy sensor."""

    _attr_icon = "mdi:flash"

    def __init__(self, data, name, sensor_type, update_call):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._sensor_type = sensor_type
        self.update_sensor = update_call
        self._state = None

        if sensor_type == ACTIVE_TYPE:
            self._unit_of_measurement = UnitOfPower.WATT
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif sensor_type == DAILY_TYPE:
            self._unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self) -> None:
        """Get the latest data, update state."""
        self.update_sensor()

        if self._sensor_type == ACTIVE_TYPE:
            self._state = self._data.active_power
        elif self._sensor_type == DAILY_TYPE:
            self._state = self._data.daily_usage
