"""The Compensation integration."""

import logging
from operator import itemgetter

import numpy as np
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    CONF_ATTRIBUTE,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_COMPENSATION,
    CONF_DATAPOINTS,
    CONF_DEGREE,
    CONF_LOWER_LIMIT,
    CONF_POLYNOMIAL,
    CONF_PRECISION,
    CONF_UPPER_LIMIT,
    DATA_COMPENSATION,
    DEFAULT_DEGREE,
    DEFAULT_PRECISION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def datapoints_greater_than_degree(value: dict) -> dict:
    """Validate data point list is greater than polynomial degrees."""
    if len(value[CONF_DATAPOINTS]) <= value[CONF_DEGREE]:
        raise vol.Invalid(
            f"{CONF_DATAPOINTS} must have at least"
            f" {value[CONF_DEGREE] + 1} {CONF_DATAPOINTS}"
        )

    return value


COMPENSATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE): cv.entity_id,
        vol.Required(CONF_DATAPOINTS): [
            vol.ExactSequence([vol.Coerce(float), vol.Coerce(float)])
        ],
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_UPPER_LIMIT, default=False): cv.boolean,
        vol.Optional(CONF_LOWER_LIMIT, default=False): cv.boolean,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): cv.positive_int,
        vol.Optional(CONF_DEGREE, default=DEFAULT_DEGREE): vol.All(
            vol.Coerce(int),
            vol.Range(min=1, max=7),
        ),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {cv.slug: vol.All(COMPENSATION_SCHEMA, datapoints_greater_than_degree)}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Compensation sensor."""
    hass.data[DATA_COMPENSATION] = {}

    for compensation, conf in config[DOMAIN].items():
        _LOGGER.debug("Setup %s.%s", DOMAIN, compensation)

        degree = conf[CONF_DEGREE]

        initial_coefficients: list[tuple[float, float]] = conf[CONF_DATAPOINTS]
        sorted_coefficients = sorted(initial_coefficients, key=itemgetter(0))

        # get x values and y values from the x,y point pairs
        x_values, y_values = zip(*initial_coefficients, strict=False)

        # try to get valid coefficients for a polynomial
        coefficients = None
        with np.errstate(all="raise"):
            try:
                coefficients = np.polyfit(x_values, y_values, degree)
            except FloatingPointError as error:
                _LOGGER.error(
                    "Setup of %s encountered an error, %s",
                    compensation,
                    error,
                )

        if coefficients is not None:
            data = {
                k: v for k, v in conf.items() if k not in [CONF_DEGREE, CONF_DATAPOINTS]
            }
            data[CONF_POLYNOMIAL] = np.poly1d(coefficients)

            if data[CONF_LOWER_LIMIT]:
                data[CONF_MINIMUM] = sorted_coefficients[0]
            else:
                data[CONF_MINIMUM] = None

            if data[CONF_UPPER_LIMIT]:
                data[CONF_MAXIMUM] = sorted_coefficients[-1]
            else:
                data[CONF_MAXIMUM] = None

            hass.data[DATA_COMPENSATION][compensation] = data

            hass.async_create_task(
                async_load_platform(
                    hass,
                    SENSOR_DOMAIN,
                    DOMAIN,
                    {CONF_COMPENSATION: compensation},
                    config,
                )
            )

    return True
