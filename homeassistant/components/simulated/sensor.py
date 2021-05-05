"""Adds a simulated sensor."""
from datetime import datetime
import math
from random import Random

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util

CONF_AMP = "amplitude"
CONF_FWHM = "spread"
CONF_MEAN = "mean"
CONF_PERIOD = "period"
CONF_PHASE = "phase"
CONF_SEED = "seed"
CONF_UNIT = "unit"
CONF_RELATIVE_TO_EPOCH = "relative_to_epoch"

DEFAULT_AMP = 1
DEFAULT_FWHM = 0
DEFAULT_MEAN = 0
DEFAULT_NAME = "simulated"
DEFAULT_PERIOD = 60
DEFAULT_PHASE = 0
DEFAULT_SEED = 999
DEFAULT_UNIT = "value"
DEFAULT_RELATIVE_TO_EPOCH = True

ICON = "mdi:chart-line"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_AMP, default=DEFAULT_AMP): vol.Coerce(float),
        vol.Optional(CONF_FWHM, default=DEFAULT_FWHM): vol.Coerce(float),
        vol.Optional(CONF_MEAN, default=DEFAULT_MEAN): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PERIOD, default=DEFAULT_PERIOD): cv.positive_int,
        vol.Optional(CONF_PHASE, default=DEFAULT_PHASE): vol.Coerce(float),
        vol.Optional(CONF_SEED, default=DEFAULT_SEED): cv.positive_int,
        vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): cv.string,
        vol.Optional(
            CONF_RELATIVE_TO_EPOCH, default=DEFAULT_RELATIVE_TO_EPOCH
        ): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the simulated sensor."""
    name = config.get(CONF_NAME)
    unit = config.get(CONF_UNIT)
    amp = config.get(CONF_AMP)
    mean = config.get(CONF_MEAN)
    period = config.get(CONF_PERIOD)
    phase = config.get(CONF_PHASE)
    fwhm = config.get(CONF_FWHM)
    seed = config.get(CONF_SEED)
    relative_to_epoch = config.get(CONF_RELATIVE_TO_EPOCH)

    sensor = SimulatedSensor(
        name, unit, amp, mean, period, phase, fwhm, seed, relative_to_epoch
    )
    add_entities([sensor], True)


class SimulatedSensor(SensorEntity):
    """Class for simulated sensor."""

    def __init__(
        self, name, unit, amp, mean, period, phase, fwhm, seed, relative_to_epoch
    ):
        """Init the class."""
        self._name = name
        self._unit = unit
        self._amp = amp
        self._mean = mean
        self._period = period
        self._phase = phase  # phase in degrees
        self._fwhm = fwhm
        self._seed = seed
        self._random = Random(seed)  # A local seeded Random
        self._start_time = (
            datetime(1970, 1, 1, tzinfo=dt_util.UTC)
            if relative_to_epoch
            else dt_util.utcnow()
        )
        self._relative_to_epoch = relative_to_epoch
        self._state = None

    def time_delta(self):
        """Return the time delta."""
        dt0 = self._start_time
        dt1 = dt_util.utcnow()
        return dt1 - dt0

    def signal_calc(self):
        """Calculate the signal."""
        mean = self._mean
        amp = self._amp
        time_delta = self.time_delta().total_seconds() * 1e6  # to milliseconds
        period = self._period * 1e6  # to milliseconds
        fwhm = self._fwhm / 2
        phase = math.radians(self._phase)
        if period == 0:
            periodic = 0
        else:
            periodic = amp * (math.sin((2 * math.pi * time_delta / period) + phase))
        noise = self._random.gauss(mu=0, sigma=fwhm)
        return round(mean + periodic + noise, 3)

    async def async_update(self):
        """Update the sensor."""
        self._state = self.signal_calc()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit

    @property
    def extra_state_attributes(self):
        """Return other details about the sensor state."""
        return {
            "amplitude": self._amp,
            "mean": self._mean,
            "period": self._period,
            "phase": self._phase,
            "spread": self._fwhm,
            "seed": self._seed,
            "relative_to_epoch": self._relative_to_epoch,
        }
