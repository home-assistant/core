"""Sensor for displaying the number of result on Shodan.io."""

from __future__ import annotations

from datetime import timedelta
import logging

import shodan
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_QUERY = "query"

DEFAULT_NAME = "Shodan Sensor"

SCAN_INTERVAL = timedelta(minutes=15)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_QUERY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Shodan sensor."""
    api_key = config[CONF_API_KEY]
    name = config[CONF_NAME]
    query = config[CONF_QUERY]

    data = ShodanData(shodan.Shodan(api_key), query)
    try:
        data.update()
    except shodan.exception.APIError as error:
        _LOGGER.warning("Unable to connect to Shodan.io: %s", error)
        return

    add_entities([ShodanSensor(data, name)], True)


class ShodanSensor(SensorEntity):
    """Representation of the Shodan sensor."""

    _attr_attribution = "Data provided by Shodan"
    _attr_icon = "mdi:tooltip-text"
    _attr_native_unit_of_measurement = "Hits"

    def __init__(self, data: ShodanData, name: str) -> None:
        """Initialize the Shodan sensor."""
        self.data = data
        self._attr_name = name

    def update(self) -> None:
        """Get the latest data and updates the states."""
        data = self.data.update()
        self._attr_native_value = data["total"]


class ShodanData:
    """Get the latest data and update the states."""

    def __init__(self, api: shodan.Shodan, query: str) -> None:
        """Initialize the data object."""
        self._api = api
        self._query = query

    def update(self):
        """Get the latest data from shodan.io."""
        return self._api.count(self._query)
