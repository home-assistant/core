"""Adds a simulated sensor."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from random import Random

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
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

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the simulated sensor."""
    name = config[CONF_NAME]
    unit = config[CONF_UNIT]
    amp = config[CONF_AMP]
    mean = config[CONF_MEAN]
    period = config[CONF_PERIOD]
    phase = config[CONF_PHASE]
    fwhm = config[CONF_FWHM]
    seed = config[CONF_SEED]
    relative_to_epoch = config[CONF_RELATIVE_TO_EPOCH]

    async_add_entities(
        [
            SimulatedSensor(
                name, unit, amp, mean, period, phase, fwhm, seed, relative_to_epoch
            )
        ],
        True,
    )


class SimulatedSensor(SensorEntity):
    """Class for simulated sensor."""

    _attr_icon = "mdi:chart-line"

    def __init__(
        self,
        name: str,
        unit: str,
        amp: float,
        mean: float,
        period: int,
        phase: float,
        fwhm: float,
        seed: int,
        relative_to_epoch: bool,
    ) -> None:
        """Init the class."""
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
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
        self._attr_extra_state_attributes = {
            "amplitude": amp,
            "mean": mean,
            "period": period,
            "phase": phase,
            "spread": fwhm,
            "seed": seed,
            "relative_to_epoch": relative_to_epoch,
        }

    def time_delta(self) -> timedelta:
        """Return the time delta."""
        dt0 = self._start_time
        dt1 = dt_util.utcnow()
        return dt1 - dt0

    def signal_calc(self) -> float:
        """Calculate the signal."""
        mean = self._mean
        amp = self._amp
        time_delta = self.time_delta().total_seconds() * 1e6  # to milliseconds
        period = self._period * 1e6  # to milliseconds
        fwhm = self._fwhm / 2
        phase = math.radians(self._phase)
        if period == 0:
            periodic = 0.0
        else:
            periodic = amp * (math.sin((2 * math.pi * time_delta / period) + phase))
        noise = self._random.gauss(mu=0, sigma=fwhm)
        return round(mean + periodic + noise, 3)

    async def async_update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self.signal_calc()
