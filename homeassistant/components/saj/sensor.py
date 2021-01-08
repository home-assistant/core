"""SAJ solar inverter interface."""
from datetime import date
import logging

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    MASS_KILOGRAMS,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
)
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL = 5
MAX_INTERVAL = 300

INVERTER_TYPES = ["ethernet", "wifi"]

SAJ_UNIT_MAPPINGS = {
    "": None,
    "h": TIME_HOURS,
    "kg": MASS_KILOGRAMS,
    "kWh": ENERGY_KILO_WATT_HOUR,
    "W": POWER_WATT,
    "°C": TEMP_CELSIUS,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=INVERTER_TYPES[0]): vol.In(INVERTER_TYPES),
        vol.Inclusive(CONF_USERNAME, "credentials"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "credentials"): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the SAJ sensors."""

    remove_interval_update = None
    wifi = config[CONF_TYPE] == INVERTER_TYPES[1]

    # Init all sensors
    sensor_def = pysaj.Sensors(wifi)

    # Use all sensors by default
    hass_sensors = []

    kwargs = {}
    if wifi:
        kwargs["wifi"] = True
        if config.get(CONF_USERNAME) and config.get(CONF_PASSWORD):
            kwargs["username"] = config[CONF_USERNAME]
            kwargs["password"] = config[CONF_PASSWORD]

    try:
        saj = pysaj.SAJ(config[CONF_HOST], **kwargs)
        done = await saj.read(sensor_def)
    except pysaj.UnauthorizedException:
        _LOGGER.error("Username and/or password is wrong")
        return
    except pysaj.UnexpectedResponseException as err:
        _LOGGER.error(
            "Error in SAJ, please check host/ip address. Original error: %s", err
        )
        return

    if not done:
        raise PlatformNotReady

    for sensor in sensor_def:
        if sensor.enabled:
            hass_sensors.append(
                SAJsensor(saj.serialnumber, sensor, inverter_name=config.get(CONF_NAME))
            )

    async_add_entities(hass_sensors)

    async def async_saj():
        """Update all the SAJ sensors."""
        values = await saj.read(sensor_def)

        for sensor in hass_sensors:
            state_unknown = False
            if not values:
                # SAJ inverters are powered by DC via solar panels and thus are
                # offline after the sun has set. If a sensor resets on a daily
                # basis like "today_yield", this reset won't happen automatically.
                # Code below checks if today > day when sensor was last updated
                # and if so: set state to None.
                # Sensors with live values like "temperature" or "current_power"
                # will also be reset to None.
                if (sensor.per_day_basis and date.today() > sensor.date_updated) or (
                    not sensor.per_day_basis and not sensor.per_total_basis
                ):
                    state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)

        return values

    def start_update_interval(event):
        """Start the update interval scheduling."""
        nonlocal remove_interval_update
        remove_interval_update = async_track_time_interval_backoff(hass, async_saj)

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


class SAJsensor(Entity):
    """Representation of a SAJ sensor."""

    def __init__(self, serialnumber, pysaj_sensor, inverter_name=None):
        """Initialize the SAJ sensor."""
        self._sensor = pysaj_sensor
        self._inverter_name = inverter_name
        self._serialnumber = serialnumber
        self._state = self._sensor.value

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._inverter_name:
            return f"saj_{self._inverter_name}_{self._sensor.name}"

        return f"saj_{self._sensor.name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SAJ_UNIT_MAPPINGS[self._sensor.unit]

    @property
    def device_class(self):
        """Return the device class the sensor belongs to."""
        if self.unit_of_measurement == POWER_WATT:
            return DEVICE_CLASS_POWER
        if (
            self.unit_of_measurement == TEMP_CELSIUS
            or self._sensor.unit == TEMP_FAHRENHEIT
        ):
            return DEVICE_CLASS_TEMPERATURE

    @property
    def should_poll(self) -> bool:
        """SAJ sensors are updated & don't poll."""
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
        return f"{self._serialnumber}_{self._sensor.name}"
