"""Support for an exposed aREST RESTful API of a device."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

CONF_FUNCTIONS = "functions"
CONF_PINS = "pins"

DEFAULT_NAME = "aREST sensor"

PIN_VARIABLE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PINS, default={}): vol.Schema(
            {cv.string: PIN_VARIABLE_SCHEMA}
        ),
        vol.Optional(CONF_MONITORED_VARIABLES, default={}): vol.Schema(
            {cv.string: PIN_VARIABLE_SCHEMA}
        ),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the aREST sensor."""
    resource = config[CONF_RESOURCE]
    var_conf = config[CONF_MONITORED_VARIABLES]
    pins = config[CONF_PINS]

    try:
        response = requests.get(resource, timeout=10).json()
    except requests.exceptions.MissingSchema:
        _LOGGER.error(
            "Missing resource or schema in configuration. Add http:// to your URL"
        )
        return
    except requests.exceptions.ConnectionError:
        _LOGGER.error("No route to device at %s", resource)
        return

    arest = ArestData(resource)

    def make_renderer(value_template):
        """Create a renderer based on variable_template value."""
        if value_template is None:
            return lambda value: value

        value_template.hass = hass

        def _render(value):
            try:
                return value_template.async_render({"value": value}, parse_result=False)
            except TemplateError:
                _LOGGER.exception("Error parsing value")
                return value

        return _render

    dev = []

    if var_conf is not None:
        for variable, var_data in var_conf.items():
            if variable not in response["variables"]:
                _LOGGER.error("Variable: %s does not exist", variable)
                continue

            renderer = make_renderer(var_data.get(CONF_VALUE_TEMPLATE))
            dev.append(
                ArestSensor(
                    arest,
                    resource,
                    config.get(CONF_NAME, response[CONF_NAME]),
                    var_data.get(CONF_NAME, variable),
                    variable=variable,
                    unit_of_measurement=var_data.get(CONF_UNIT_OF_MEASUREMENT),
                    renderer=renderer,
                )
            )

    if pins is not None:
        for pinnum, pin in pins.items():
            renderer = make_renderer(pin.get(CONF_VALUE_TEMPLATE))
            dev.append(
                ArestSensor(
                    ArestData(resource, pinnum),
                    resource,
                    config.get(CONF_NAME, response[CONF_NAME]),
                    pin.get(CONF_NAME),
                    pin=pinnum,
                    unit_of_measurement=pin.get(CONF_UNIT_OF_MEASUREMENT),
                    renderer=renderer,
                )
            )

    add_entities(dev, True)


class ArestSensor(SensorEntity):
    """Implementation of an aREST sensor for exposed variables."""

    def __init__(
        self,
        arest,
        resource,
        location,
        name,
        variable=None,
        pin=None,
        unit_of_measurement=None,
        renderer=None,
    ):
        """Initialize the sensor."""
        self.arest = arest
        self._attr_name = f"{location.title()} {name.title()}"
        self._variable = variable
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._renderer = renderer

        if pin is not None:
            request = requests.get(f"{resource}/mode/{pin}/i", timeout=10)
            if request.status_code != HTTPStatus.OK:
                _LOGGER.error("Can't set mode of %s", resource)

    def update(self) -> None:
        """Get the latest data from aREST API."""
        self.arest.update()
        self._attr_available = self.arest.available
        values = self.arest.data
        if "error" in values:
            self._attr_native_value = values["error"]
        else:
            self._attr_native_value = self._renderer(
                values.get("value", values.get(self._variable, None))
            )


class ArestData:
    """The Class for handling the data retrieval for variables."""

    def __init__(self, resource, pin=None):
        """Initialize the data object."""
        self._resource = resource
        self._pin = pin
        self.data = {}
        self._attr_available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from aREST device."""
        try:
            if self._pin is None:
                response = requests.get(self._resource, timeout=10)
                self.data = response.json()["variables"]
            else:
                try:
                    if str(self._pin[0]) == "A":
                        response = requests.get(
                            f"{self._resource}/analog/{self._pin[1:]}", timeout=10
                        )
                        self.data = {"value": response.json()["return_value"]}
                except TypeError:
                    response = requests.get(
                        f"{self._resource}/digital/{self._pin}", timeout=10
                    )
                    self.data = {"value": response.json()["return_value"]}
            self._attr_available = True
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device %s", self._resource)
            self._attr_available = False
