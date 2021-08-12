"""Solart Frontier Inverter interface."""
from __future__ import annotations

from datetime import date, datetime
import logging

import pysolarfrontier
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL = 60
MAX_INTERVAL = 500

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_HOST): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Solar Frontier sensors."""

    remove_interval_update = None
    sensor_def = pysolarfrontier.Sensors()
    hass_sensors = []

    try:
        pysf = pysolarfrontier.SF(config[CONF_HOST])
        done = await pysf.read(sensor_def)
    except (pysolarfrontier.UnexpectedResponseException) as err:
        _LOGGER.error(
            "Unexpected response received from Solar Frontier. " "Original error: %s",
            err,
        )
        return
    except (pysolarfrontier.ConnectionErrorException) as err:
        _LOGGER.error(
            "Error in Solar Frontier, please check host/ip address. "
            "Original error: %s",
            err,
        )
        return

    if not done:
        raise PlatformNotReady

    for sensor in sensor_def:
        if sensor.name == "total_yield":
            continue
        if sensor.enabled:
            hass_sensors.append(SFsensor(sensor, inverter_name=config.get(CONF_NAME)))

    async_add_entities(hass_sensors)

    async def async_sf():
        """Update all the Solar Frontier sensors."""
        values = await pysf.read(sensor_def)

        for sensor in hass_sensors:
            sensor.async_update_values()

        return values

    def start_update_interval(event):
        """Start the update interval scheduling."""
        nonlocal remove_interval_update
        remove_interval_update = async_track_time_interval_backoff(hass, async_sf)

    def stop_update_interval(event):
        """Properly cancel the scheduled update."""
        remove_interval_update()  # pylint: disable=not-callable

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_update_interval)
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, stop_update_interval)


@callback
def async_track_time_interval_backoff(hass, action) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively and increases the interval when failed."""

    remove = None
    interval = MIN_INTERVAL

    async def interval_listener(now=None):
        """Handle elapsed interval with backoff."""
        nonlocal interval, remove
        try:
            if await action():
                interval = MIN_INTERVAL
            else:
                interval = min(interval * 2, MAX_INTERVAL)
        finally:
            remove = async_call_later(hass, interval, interval_listener)

    hass.async_create_task(interval_listener())

    def remove_listener():
        """Remove interval listener."""
        if remove:
            remove()  # pylint: disable=not-callable

    return remove_listener


class SFsensor(SensorEntity):
    """Representation of a Solar Frontier sensor."""

    def __init__(self, pysf_sensor, inverter_name=None):
        """Initialize the Solar Frontier sensor."""
        self._sensor = pysf_sensor
        self._inverter_name = inverter_name
        self._state = self._sensor.value

        if pysf_sensor.name in ("today_yield", "month_yield", "year_yield"):
            self._attr_state_class = STATE_CLASS_MEASUREMENT
        if pysf_sensor.name == "total_yield":
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._inverter_name:
            return f"solar_frontier_{self._inverter_name}_{self._sensor.name}"

        return f"solar_frontier_{self._sensor.name}"

    @property
    def state(self):
        """Return value of sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor.unit

    @property
    def device_class(self):
        """Return the device class the sensor belongs to."""
        if self.unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            return DEVICE_CLASS_ENERGY

    @property
    def should_poll(self) -> bool:
        """Solar Frontier sensors are updated & don't poll."""
        return False

    @property
    def per_day_basis(self) -> bool:
        """Return if the sensors value is on daily basis or not."""
        return self._sensor.per_day_basis

    @property
    def per_total_basis(self) -> bool:
        """Return if the sensors value is cumulative or not."""
        return self._sensor.per_total_basis

    @property
    def date_updated(self) -> date:
        """Return the date when the sensor was last updated."""
        return self._sensor.date

    @callback
    def async_update_values(self):
        """Update this sensor."""

        last_reset_today = datetime.today().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        last_reset_month = last_reset_today.replace(day=1)
        last_reset_year = last_reset_month.replace(month=1)

        if self._sensor.name == "today_yield":
            self._attr_last_reset = last_reset_today
        if self._sensor.name == "month_yield":
            self._attr_last_reset = last_reset_month
        if self._sensor.name == "year_yield":
            self._attr_last_reset = last_reset_year
        self._state = self._sensor.value

        self.async_write_ha_state()
