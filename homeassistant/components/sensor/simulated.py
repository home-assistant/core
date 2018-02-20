"""
Adds a simulated sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.simulated/
"""
import logging
import numpy as np
import datetime as datetime

import voluptuous as vol

from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.components.sensor import PLATFORM_SCHEMA

REQUIREMENTS = ['numpy==1.14.0']

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = datetime.timedelta(seconds=1)
ICON = 'mdi:chart-line'

CONF_UNIT = 'unit'
CONF_AMP = 'amplitude'
CONF_MEAN = 'mean'
CONF_PERIOD = 'period'
CONF_PHASE = 'phase'
CONF_FWHM = 'spread'
CONF_SEED = 'seed'

DEFAULT_NAME = 'simulated'
DEFAULT_UNIT = 'value'
DEFAULT_AMP = 1
DEFAULT_MEAN = 0
DEFAULT_PERIOD = datetime.timedelta(seconds=60)
DEFAULT_PHASE = 0
DEFAULT_FWHM = 0.0
DEFAULT_SEED = None


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT, default=DEFAULT_UNIT): cv.string,
    vol.Optional(CONF_AMP, default=DEFAULT_AMP): vol.Coerce(float),
    vol.Optional(CONF_MEAN, default=DEFAULT_MEAN): vol.Coerce(float),
    vol.Optional(CONF_PERIOD, default=DEFAULT_PERIOD): cv.time_period_seconds,
    vol.Optional(CONF_PHASE, default=DEFAULT_PHASE): vol.Coerce(float),
    vol.Optional(CONF_FWHM, default=DEFAULT_FWHM): vol.Coerce(float),
    vol.Optional(CONF_SEED, default=DEFAULT_SEED): cv.positive_int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the simulated sensor."""
    name = config.get(CONF_NAME)
    unit = config.get(CONF_UNIT)
    amp = config.get(CONF_AMP)
    mean = config.get(CONF_MEAN)
    period = config.get(CONF_PERIOD)
    phase = config.get(CONF_PHASE)
    fwhm = config.get(CONF_FWHM)
    seed = config.get(CONF_SEED)

    if seed:
        np.random.seed(seed)  # If a seed is configured, apply.

    sensor = SimulatedSensor(
        name, unit, amp, mean, period, phase, fwhm, seed
        )
    add_devices([sensor], True)


class SimulatedSensor(Entity):
    """Class for simulated sensor."""

    def __init__(self, name, unit, amp, mean, period, phase, fwhm, seed):
        """Init the class."""
        self._name = name
        self._unit = unit
        self._amp = amp
        self._mean = mean
        self._period = period
        self._phase = phase  # phase in degrees
        self._fwhm = fwhm
        self._seed = seed
        self._start_time = datetime.datetime.now()
        self._state = None

    def time_delta(self):
        """"Return the time difference between the current measurement
        and the start of the session."""
        dt0 = self._start_time
        dt1 = datetime.datetime.now()
        return dt1 - dt0

    def signal_calc(self):
        m0 = self._mean
        a0 = self._amp
        dt = self.time_delta().total_seconds()*1e6  # convert to  milliseconds
        w0 = self._period.total_seconds()*1e6
        s0 = self._fwhm/2
        p0 = self._phase*np.pi/180  # Convert to radians
        periodic = a0 * (np.sin((2*np.pi*dt/w0) + p0))
        noise = np.random.normal(0, s0)
        return m0 + periodic + noise

    def update(self):
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
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        attr = {
            'amplitude': self._amp,
            'mean': self._mean,
            'period': str(int(self._period.total_seconds())) + " seconds",
            'phase': str(self._phase) + " degrees",
            'spread': self._fwhm,
            'seed': self._seed,
            }
        return attr
