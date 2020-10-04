"""SAJ solar inverter interface."""
import asyncio
from datetime import date
import logging

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MASS_KILOGRAMS,
    POWER_WATT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
)
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN, INVERTER_TYPES

_LOGGER = logging.getLogger(__name__)

# seconds
MIN_INTERVAL = 30
MAX_INTERVAL = 900

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up for SAJ inverters."""
    await async_setup_platform(hass, entry.data, async_add_entities)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Set up the SAJ sensors."""
    inverter = SAJInverter(config)
    await inverter.connect()
    inverter.setup(hass, async_add_entities)


class SAJInverter:
    """Representation of a SAJ inverter."""

    def __init__(self, config):
        """Init SAJ Inverter class."""
        self._name = config.get(CONF_NAME)
        self._wifi = config[CONF_TYPE] == INVERTER_TYPES[1]

        kwargs = {}
        if self._wifi:
            kwargs["wifi"] = True
            if config.get(CONF_USERNAME) and config.get(CONF_PASSWORD):
                kwargs["username"] = config[CONF_USERNAME]
                kwargs["password"] = config[CONF_PASSWORD]

        self._saj = pysaj.SAJ(config[CONF_HOST], **kwargs)
        self._sensor_def = pysaj.Sensors(self._wifi)

        self._hass = None
        self._hass_sensors = []
        self._interval = MIN_INTERVAL
        self._stop_interval = None

    @property
    def name(self):
        """Return the name of the inverter."""
        return self._name

    @property
    def serialnumber(self):
        """Return the serial number of the inverter."""
        return self._saj.serialnumber

    async def connect(self):
        """Try to connect to the inverter."""
        done = await self._saj.read(self._sensor_def)
        if done:
            return

        raise CannotConnect

    def setup(self, hass, async_add_entities):
        """Add sensors to Core and start update loop."""
        self._hass = hass
        for sensor in self._sensor_def:
            if sensor.enabled:
                self._hass_sensors.append(SAJSensor(self, sensor))

        async_add_entities(self._hass_sensors)

        if self._hass.state == CoreState.running:
            self.start_update_interval(None)
        else:
            self._hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, self.start_update_interval
            )
        self._hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, self.stop_update_interval)

    async def update(self):
        """Update all the SAJ sensors."""
        values = await self._saj.read(self._sensor_def)

        for sensor in self._hass_sensors:
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

    def start_update_interval(self, _):
        """Start the update interval scheduling."""
        self._stop_interval = async_call_later(
            self._hass, self._interval, self._interval_listener
        )

    def stop_update_interval(self, _):
        """Properly cancel the scheduled update."""
        if self._stop_interval:
            self._stop_interval()
            self._stop_interval = None

    async def _interval_listener(self, _):
        try:
            if await self.update():
                self._connected = True
                self._interval = MIN_INTERVAL
            else:
                self._connected = False
                self._interval = min(self._interval * 2, MAX_INTERVAL)
        except asyncio.exceptions.TimeoutError:
            pass
        finally:
            self._stop_interval = async_call_later(
                self._hass, self._interval, self._interval_listener
            )


class SAJSensor(Entity):
    """Representation of a SAJ sensor."""

    def __init__(self, inverter: SAJInverter, pysaj_sensor):
        """Initialize the SAJ sensor."""
        self._inverter = inverter
        self._sensor = pysaj_sensor
        self._state = self._sensor.value

    async def async_will_remove_from_hass(self) -> None:
        """Stop update loop."""
        self._inverter.stop_update_interval(None)

    @property
    def name(self):
        """Return the name of the sensor."""
        if self._inverter.name:
            return f"saj_{self._inverter.name}_{self._sensor.name}"

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
        return f"{self._inverter.serialnumber}_{self._sensor.name}"

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self._inverter.serialnumber)
            },
            "name": "SAJ Solar Inverter",
            "manufacturer": "SAJ",
        }


class CannotConnect(PlatformNotReady):
    """Error to indicate we cannot connect."""
