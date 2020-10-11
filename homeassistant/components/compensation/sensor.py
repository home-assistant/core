"""Support for compensation sensor."""
import numpy as np
import re
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_ENTITY_ID,
    CONF_ENTITY_ID,
    CONF_NAME,
    CONF_ATTRIBUTE,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_DEGREE,
    CONF_PRECISION,
    MATCH_DATAPOINT,
    DEFAULT_DEGREE,
    DEFAULT_PRECISION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

ATTR_ATTRIBUTE = "attribute"
ATTR_COEFFICIENTS = "coefficients"

CONF_DATAPOINTS = "data_points"


def datapoints_greater_than_degree(value: dict) -> dict:
    """Validate data point list is greater than polynomial degrees."""
    if not len(value[CONF_DATAPOINTS]) > value[CONF_DEGREE]:
        raise vol.Invalid(
            f"{CONF_DATAPOINTS} must have at least {value[CONF_DEGREE]+1} {CONF_DATAPOINTS}"
        )

    return value


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_DATAPOINTS): vol.All(
                cv.ensure_list(cv.matches_regex(MATCH_DATAPOINT)),
            ),
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_ATTRIBUTE): cv.string,
            vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): cv.positive_int,
            vol.Optional(CONF_DEGREE, default=DEFAULT_DEGREE): vol.All(
                vol.Coerce(int),
                vol.Range(min=1, max=7),
            ),
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        }
    ),
    datapoints_greater_than_degree,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Compensation sensor."""

    compensation = CompensationSensor(
        hass,
        config[CONF_ENTITY_ID],
        config.get(CONF_NAME),
        config.get(CONF_ATTRIBUTE),
        config[CONF_PRECISION],
        config[CONF_DEGREE],
        config[CONF_DATAPOINTS],
        config.get(CONF_UNIT_OF_MEASUREMENT),
    )

    async_add_entities([compensation], True)


class CompensationSensor(Entity):
    """Representation of a Compensation sensor."""

    def __init__(
        self,
        hass,
        entity_id,
        name,
        attribute,
        precision,
        degree,
        datapoints,
        unit_of_measurement,
    ):
        """Initialize the Compensation sensor."""
        self._entity_id = entity_id
        self._name = name
        self._precision = precision
        self._attribute = attribute
        self._unit_of_measurement = unit_of_measurement

        self._points = []
        for datapoint in datapoints:
            match = re.match(MATCH_DATAPOINT, datapoint)
            # we should always have x and y if the regex validation passed.
            x_value, y_value = [float(v) for v in match.groups()]
            self._points.append((x_value, y_value))

        x_values, y_values = zip(*self._points)
        self._coefficients = np.polyfit(x_values, y_values, degree)
        self._poly = np.poly1d(self._coefficients)

        self._state = STATE_UNKNOWN

        @callback
        def async_compensation_sensor_state_listener(event):
            """Handle sensor state changes."""
            new_state = event.data.get("new_state")
            if new_state is None:
                return

            if self._unit_of_measurement is None and self._attribute is None:
                self._unit_of_measurement = new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT
                )

            try:
                if self._attribute:
                    value = float(new_state.attributes.get(self._attribute))
                else:
                    value = (
                        None
                        if new_state.state == STATE_UNKNOWN
                        else float(new_state.state)
                    )
                # Calculate the result
                self._state = round(self._poly(value), self._precision)

            except (ValueError, TypeError):
                self._state = STATE_UNKNOWN
                if self._attribute:
                    _LOGGER.warning(
                        "%s attribute %s is not numerical",
                        self._entity_id,
                        self._attribute,
                    )
                else:
                    _LOGGER.warning("%s state is not numerical", self._entity_id)

            self.async_write_ha_state()

        async_track_state_change_event(
            hass, [entity_id], async_compensation_sensor_state_listener
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        ret = {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_COEFFICIENTS: self._coefficients.tolist(),
        }
        if self._attribute:
            ret[ATTR_ATTRIBUTE] = self._attribute
        return ret

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement
