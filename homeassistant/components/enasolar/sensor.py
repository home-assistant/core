"""EnaSolar solar inverter interface."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Callable

import pyenasolar

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    POWER_KILO_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_MAX_OUTPUT,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    DEFAULT_SUN_DOWN,
    DEFAULT_SUN_UP,
    ENASOLAR_UNIT_MAPPINGS,
    SCAN_DATA_MIN_INTERVAL,
    SCAN_MAX_INTERVAL,
    SCAN_METERS_MIN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add enasolar entry."""

    # Use all sensors by default, but split them to have two update frequencies
    hass_meter_sensors = []
    hass_data_sensors = []

    host = config_entry.data[CONF_HOST]

    _LOGGER.debug("Instantiate an EnaSolar Inverter at '%s'", host)
    enasolar = pyenasolar.EnaSolar()

    try:
        await enasolar.interogate_inverter(host)
    except Exception as conerr:
        _LOGGER.error("Connection to EnaSolar Inverter '%s' failed (%s)", host, conerr)
        raise PlatformNotReady from conerr

    if config_entry.options != {}:
        enasolar.sun_up = dt_util.parse_time(config_entry.options[CONF_SUN_UP])
        enasolar.sun_down = dt_util.parse_time(config_entry.options[CONF_SUN_DOWN])
    else:
        enasolar.sun_up = dt_util.parse_time(DEFAULT_SUN_UP)
        enasolar.sun_down = dt_util.parse_time(DEFAULT_SUN_DOWN)

    enasolar.capability = config_entry.data[CONF_CAPABILITY]
    enasolar.dc_strings = config_entry.data[CONF_DC_STRINGS]
    enasolar.max_output = config_entry.data[CONF_MAX_OUTPUT]

    _LOGGER.debug("   Polling between %s and %s", enasolar.sun_up, enasolar.sun_down)
    _LOGGER.debug(
        "   Max Output: %s, DC Strings: %s, Capability: %s",
        enasolar.max_output,
        enasolar.dc_strings,
        enasolar.capability,
    )

    enasolar.setup_sensors()
    for sensor in enasolar.sensors:
        _LOGGER.debug("Setup sensor %s", sensor.key)
        if sensor.enabled:
            if sensor.is_meter:
                hass_meter_sensors.append(
                    EnaSolarSensor(
                        sensor, config_entry.data[CONF_NAME], enasolar.serial_no
                    )
                )
            else:
                hass_data_sensors.append(
                    EnaSolarSensor(
                        sensor, config_entry.data[CONF_NAME], enasolar.serial_no
                    )
                )

    async_add_entities([*hass_meter_sensors, *hass_data_sensors])

    async def async_enasolar_meters():
        """Update the EnaSolar Meter sensors."""

        if enasolar.sun_up <= datetime.now().time() <= enasolar.sun_down:
            values = await enasolar.read_meters()
        else:
            values = False

        for sensor in hass_meter_sensors:
            state_unknown = False
            if not values and (
                (sensor.sensor.per_day_basis and date.today() > sensor.sensor.date)
                or (
                    not sensor.sensor.per_day_basis
                    and not sensor.sensor.per_total_basis
                )
            ):
                state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)
            _LOGGER.debug(
                "Meter Sensor %s updated => %s", sensor.sensor.key, sensor.native_value
            )
        return values

    async def async_enasolar_data():
        """Update the EnaSolar Data sensors."""

        if enasolar.sun_up <= datetime.now().time() <= enasolar.sun_down:
            values = await enasolar.read_data()
        else:
            values = False

        for sensor in hass_data_sensors:
            state_unknown = False
            if not values and (
                (sensor.sensor.per_day_basis and date.today() > sensor.sensor.date)
                or (
                    not sensor.sensor.per_day_basis
                    and not sensor.sensor.per_total_basis
                )
            ):
                state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)
            _LOGGER.debug(
                "Data Sensor %s updated => %s", sensor.sensor.key, sensor.native_value
            )
        return values

    def start_update_interval(event):
        """Start the update interval scheduling."""
        config_entry.async_on_unload(
            async_track_time_interval_backoff(
                hass, async_enasolar_meters, SCAN_METERS_MIN_INTERVAL
            )
        )
        config_entry.async_on_unload(
            async_track_time_interval_backoff(
                hass, async_enasolar_data, SCAN_DATA_MIN_INTERVAL
            )
        )

    if hass.is_running:
        start_update_interval(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_update_interval)


@callback
def async_track_time_interval_backoff(hass, action, min_interval) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively and increases the interval when failed."""
    remove: type = Callable  # type: ignore
    interval = min_interval

    async def interval_listener(now=None):
        """Handle elapsed interval with backoff."""
        nonlocal interval, remove

        try:
            if await action():
                interval = min_interval
            else:
                interval = min(interval * 2, SCAN_MAX_INTERVAL)
        finally:
            remove = async_call_later(hass, interval, interval_listener)

    hass.async_create_task(interval_listener())

    def remove_listener():
        """Remove interval listener."""
        if remove:
            remove()

    return remove_listener


class EnaSolarSensor(SensorEntity):
    """Representation of a EnaSolar sensor."""

    def __init__(self, pyenasolar_sensor, inverter_name=None, serial_no=None):
        """Initialize the EnaSolar sensor."""
        self.sensor = pyenasolar_sensor
        self._inverter_name = inverter_name
        self.serial_no = serial_no
        self._native_value = self.sensor.value

        if pyenasolar_sensor.is_meter:
            self._attr_state_class = STATE_CLASS_MEASUREMENT
        else:
            self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
        self._attr_native_unit_of_measurement = ENASOLAR_UNIT_MAPPINGS[self.sensor.unit]
        self._attr_should_poll = False

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._inverter_name:
            return f"enasolar_{self._inverter_name}_{self.sensor.name}"

        return f"enasolar_{self.sensor.name}"

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self._native_value

    @property
    def device_class(self):
        """Return the device class the sensor belongs to."""
        if self._attr_native_unit_of_measurement == POWER_KILO_WATT:
            return DEVICE_CLASS_POWER
        if self._attr_native_unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            return DEVICE_CLASS_ENERGY
        if (
            self._attr_unit_of_measurement == TEMP_CELSIUS
            or self._attr_unit_of_measurement == TEMP_FAHRENHEIT
        ):
            return DEVICE_CLASS_TEMPERATURE

    @callback
    def async_update_values(self, unknown_state=False):
        """Update this sensor."""
        update = False

        if self.sensor.value != self._native_value:
            update = True
            self._native_value = self.sensor.value

        if unknown_state and self._native_value is not None:
            update = True
            self.native_value = None

        if update:
            self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self.serial_no}_{self.sensor.name}"
