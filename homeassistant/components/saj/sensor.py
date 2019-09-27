"""SAJ solar inverter interface."""
import asyncio
from datetime import date, timedelta
import logging

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

SENSOR_ICON = "mdi:solar-power"


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {vol.Required(CONF_HOST): cv.string}, extra=vol.PREVENT_EXTRA
    )
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up SAJ sensors."""

    # Init all sensors
    sensor_def = pysaj.Sensors()

    # Use all sensors by default
    hass_sensors = []
    used_sensors = []

    for sensor in sensor_def:
        hass_sensors.append(SAJsensor(sensor))
        used_sensors.append(sensor)

    saj = pysaj.SAJ(config[CONF_HOST])

    async_add_entities(hass_sensors)

    backoff = 0
    backoff_step = 0

    async def async_saj(event):
        """Update all the SAJ sensors."""
        nonlocal backoff, backoff_step
        tasks = []
        # If reading sensors has failed multiple times
        if backoff > 1:
            backoff -= 1

            # SAJ inverters are powered by DC via solar panels and thus are
            # offline after the sun has set. If a sensor resets on a daily
            # basis like "today_yield", this reset won't happen automatically.
            # Code below checks if today > day when sensor was last updated
            # and if so: set state to STATE_UNKNOWN.
            # Sensors with live values like "temperature" or "current_power"
            # will also be reset to STATE_UNKNOWN.
            for sensor in hass_sensors:
                if (sensor.per_day_basis and date.today() > sensor.date_updated) or (
                    not sensor.per_day_basis and not sensor.per_total_basis
                ):
                    task = sensor.async_update_values(unkown_state=True)
                    if task:
                        tasks.append(task)
            if tasks:
                await asyncio.wait(tasks)

            return

        values = await saj.read(used_sensors)
        if not values:
            try:
                backoff = [1, 1, 1, 6, 30][backoff_step]
                backoff_step += 1
            except IndexError:
                backoff = 60
            return
        backoff_step = 0

        for sensor in hass_sensors:
            task = sensor.async_update_values()
            if task:
                tasks.append(task)
        if tasks:
            await asyncio.wait(tasks)

    interval = config.get(CONF_SCAN_INTERVAL) or timedelta(seconds=5)
    async_track_time_interval(hass, async_saj, interval)


class SAJsensor(Entity):
    """Representation of a SAJ sensor."""

    def __init__(self, pysaj_sensor):
        """Initialize the sensor."""
        self._sensor = pysaj_sensor
        self._state = self._sensor.value

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"saj_{self._sensor.name}"

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return SENSOR_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor.unit

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
        """Return if the sensors value is cummulative or not."""
        return self._sensor.per_total_basis

    @property
    def date_updated(self) -> date:
        """Return the date when the sensor was last updated."""
        return self._sensor.date

    def async_update_values(self, unkown_state=False):
        """Update this sensor."""
        update = False

        if self._sensor.value != self._state:
            update = True
            self._state = self._sensor.value

        if unkown_state and self._state is not None:
            update = True
            self._state = None

        return self.async_update_ha_state() if update else None

    @property
    def unique_id(self):
        """Return a unique identifier for this sensor."""
        return f"{self._sensor.name}"
