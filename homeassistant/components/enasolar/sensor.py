"""EnaSolar solar inverter interface."""
from __future__ import annotations

# from datetime import time
from datetime import date, datetime
import logging

import pyenasolar
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
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_MAX_OUTPUT,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    ENASOLAR_UNIT_MAPPINGS,
    SCAN_DATA_MIN_INTERVAL,
    SCAN_MAX_INTERVAL,
    SCAN_METERS_MIN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_SUN_DOWN, default="22:00"): cv.time,
        vol.Required(CONF_SUN_UP, default="5:00"): cv.time,
        vol.Optional(CONF_MAX_OUTPUT): vol.In([1.5, 2.0, 3.0, 3.8, 4.0, 5.0]),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_DC_STRINGS): vol.In([1, 2]),
        vol.Optional(CONF_CAPABILITY): cv.positive_int,
    }
)


async def async_setup_platform(  # noqa: C901
    hass, config, async_add_entities, discovery_info=None
):
    """Set up the EnaSolar sensors."""

    remove_interval_update_meters = None
    remove_interval_update_data = None

    # Use all sensors by default
    hass_meter_sensors = []
    hass_data_sensors = []

    kwargs = {}

    try:
        _LOGGER.info(
            "Attempting to set up monitoring of EnaSolar Inverter at '%s'",
            config[CONF_HOST],
        )
        enasolar = pyenasolar.EnaSolar(config[CONF_HOST], **kwargs)
        done = await enasolar.model()

        enasolar.sun_up = config[CONF_SUN_UP]
        enasolar.sun_down = config[CONF_SUN_DOWN]

        try:
            if config[CONF_CAPABILITY] is not None:
                enasolar.capability = config[CONF_CAPABILITY]
        except KeyError:
            pass

        try:
            if config[CONF_DC_STRINGS] is not None:
                enasolar.dc_strings = config[CONF_DC_STRINGS]
        except KeyError:
            pass

        try:
            if config[CONF_MAX_OUTPUT] is not None:
                enasolar.max_output = config[CONF_MAX_OUTPUT]
        except KeyError:
            pass

    except pyenasolar.UnexpectedResponseException as err:
        _LOGGER.error(
            "Error in EnaSolar, please check host/ip address. Original error: %s", err
        )
        return

    if not done:
        raise PlatformNotReady

    for sensor in enasolar.sensors:
        _LOGGER.debug("Setup sensor %s", sensor.key)
        if sensor.enabled:
            if sensor.is_meter:
                hass_meter_sensors.append(
                    EnaSolarSensor(sensor, inverter_name=config.get(CONF_NAME))
                )
            else:
                hass_data_sensors.append(
                    EnaSolarSensor(sensor, inverter_name=config.get(CONF_NAME))
                )

    async_add_entities(hass_meter_sensors)
    async_add_entities(hass_data_sensors)

    async def async_enasolar_meters():
        """Update the EnaSolar Meter sensors."""

        if enasolar.sun_up <= datetime.now().time() <= enasolar.sun_down:
            values = await enasolar.read_meters()
        else:
            values = False

        for sensor in hass_meter_sensors:
            state_unknown = False
            if not values and (
                (sensor.per_day_basis and date.today() > sensor.date_updated)
                or (not sensor.per_day_basis and not sensor.per_total_basis)
            ):
                state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)
            _LOGGER.debug(
                "Meter Sensor %s updated => %s", sensor._sensor.key, sensor.state
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
                (sensor.per_day_basis and date.today() > sensor.date_updated)
                or (not sensor.per_day_basis and not sensor.per_total_basis)
            ):
                state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)
            _LOGGER.debug(
                "Data Sensor %s updated => %s", sensor._sensor.key, sensor.state
            )

        return values

    def start_update_interval(event):
        """Start the update interval scheduling."""
        nonlocal remove_interval_update_meters, remove_interval_update_data

        remove_interval_update_meters = async_track_time_interval_backoff(
            hass, async_enasolar_meters, SCAN_METERS_MIN_INTERVAL
        )
        remove_interval_update_data = async_track_time_interval_backoff(
            hass, async_enasolar_data, SCAN_DATA_MIN_INTERVAL
        )

    def stop_update_interval(event):
        """Properly cancel the scheduled update."""
        remove_interval_update_meters()  # pylint: disable=not-callable
        remove_interval_update_data()  # pylint: disable=not-callable

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_update_interval)
    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, stop_update_interval)


@callback
def async_track_time_interval_backoff(hass, action, min_interval) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively and increases the interval when failed."""
    remove = None
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
            remove()  # pylint: disable=not-callable

    return remove_listener


class EnaSolarSensor(SensorEntity):
    """Representation of a EnaSolar sensor."""

    def __init__(self, pyenasolar_sensor, inverter_name=None):
        """Initialize the EnaSolar sensor."""
        self._sensor = pyenasolar_sensor
        self._inverter_name = inverter_name
        self._state = self._sensor.value

        if pyenasolar_sensor.name in ("total_energy", "temperature"):
            self._attr_state_class = STATE_CLASS_MEASUREMENT
        if pyenasolar_sensor.name == "total_energy":
            self._attr_last_reset = dt_util.utc_from_timestamp(0)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._inverter_name:
            return f"enasolar_{self._inverter_name}_{self._sensor.name}"

        return f"enasolar_{self._sensor.name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return ENASOLAR_UNIT_MAPPINGS[self._sensor.unit]

    @property
    def device_class(self):
        """Return the device class the sensor belongs to."""
        if self.unit_of_measurement == POWER_WATT:
            return DEVICE_CLASS_POWER
        if self.unit_of_measurement == ENERGY_KILO_WATT_HOUR:
            return DEVICE_CLASS_ENERGY
        if (
            self.unit_of_measurement == TEMP_CELSIUS
            or self._sensor.unit == TEMP_FAHRENHEIT
        ):
            return DEVICE_CLASS_TEMPERATURE

    @property
    def should_poll(self) -> bool:
        """Enasolar sensors are updated & don't poll."""
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
    def async_update_values(self, unknown_state=False):
        """Update this sensor."""
        update = False

        if self._sensor.value != self._state:
            update = True
            self._state = self._sensor.value

        if unknown_state and self._state is not None:
            update = True
            self._state = None

        if update:
            self.async_write_ha_state()

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self._sensor.name}"
