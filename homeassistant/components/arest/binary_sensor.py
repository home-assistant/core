"""Support for an exposed aREST RESTful API of a device."""

from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging

import requests
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_PIN, CONF_RESOURCE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_PIN): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the aREST binary sensor."""
    resource = config[CONF_RESOURCE]
    pin = config[CONF_PIN]
    device_class = config.get(CONF_DEVICE_CLASS)

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

    arest = ArestData(resource, pin)

    add_entities(
        [
            ArestBinarySensor(
                arest,
                resource,
                config.get(CONF_NAME, response[CONF_NAME]),
                device_class,
                pin,
            )
        ],
        True,
    )


class ArestBinarySensor(BinarySensorEntity):
    """Implement an aREST binary sensor for a pin."""

    def __init__(self, arest, resource, name, device_class, pin):
        """Initialize the aREST device."""
        self.arest = arest
        self._attr_name = name
        self._attr_device_class = device_class

        if pin is not None:
            request = requests.get(f"{resource}/mode/{pin}/i", timeout=10)
            if request.status_code != HTTPStatus.OK:
                _LOGGER.error("Can't set mode of %s", resource)

    def update(self) -> None:
        """Get the latest data from aREST API."""
        self.arest.update()
        self._attr_is_on = bool(self.arest.data.get("state"))


class ArestData:
    """Class for handling the data retrieval for pins."""

    def __init__(self, resource, pin):
        """Initialize the aREST data object."""
        self._resource = resource
        self._pin = pin
        self.data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from aREST device."""
        try:
            response = requests.get(f"{self._resource}/digital/{self._pin}", timeout=10)
            self.data = {"state": response.json()["return_value"]}
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to device '%s'", self._resource)
