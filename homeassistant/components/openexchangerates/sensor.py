"""Support for openexchangerates.org exchange rates service."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_BASE, CONF_NAME, CONF_QUOTE
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)
_RESOURCE = "https://openexchangerates.org/api/latest.json"

ATTRIBUTION = "Data provided by openexchangerates.org"

DEFAULT_BASE = "USD"
DEFAULT_NAME = "Exchange Rate Sensor"

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUOTE): cv.string,
        vol.Optional(CONF_BASE, default=DEFAULT_BASE): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Open Exchange Rates sensor."""
    name: str = config[CONF_NAME]
    api_key: str = config[CONF_API_KEY]
    base: str = config[CONF_BASE]
    quote: str = config[CONF_QUOTE]

    parameters = {"base": base, "app_id": api_key}

    rest = OpenexchangeratesData(_RESOURCE, parameters, quote)
    response = requests.get(_RESOURCE, params=parameters, timeout=10)

    if response.status_code != HTTPStatus.OK:
        _LOGGER.error("Check your OpenExchangeRates API key")
        return

    rest.update()
    add_entities([OpenexchangeratesSensor(rest, name, quote)], True)


class OpenexchangeratesSensor(SensorEntity):
    """Representation of an Open Exchange Rates sensor."""

    _attr_attribution = ATTRIBUTION

    def __init__(self, rest: OpenexchangeratesData, name: str, quote: str) -> None:
        """Initialize the sensor."""
        self.rest = rest
        self._name = name
        self._quote = quote
        self._state: float | None = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return other attributes of the sensor."""
        attr = self.rest.data

        return attr

    def update(self) -> None:
        """Update current conditions."""
        self.rest.update()
        if (value := self.rest.data) is None:
            self._attr_available = False
            return

        self._attr_available = True
        self._state = round(value[self._quote], 4)


class OpenexchangeratesData:
    """Get data from Openexchangerates.org."""

    def __init__(self, resource: str, parameters: dict[str, str], quote: str) -> None:
        """Initialize the data object."""
        self._resource = resource
        self._parameters = parameters
        self._quote = quote
        self.data: dict[str, Any] | None = None

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from openexchangerates.org."""
        try:
            result = requests.get(self._resource, params=self._parameters, timeout=10)
            self.data = result.json()["rates"]
        except requests.exceptions.HTTPError:
            _LOGGER.error("Check the Openexchangerates API key")
            self.data = None
