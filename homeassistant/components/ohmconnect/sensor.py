"""Support for OhmConnect."""
from __future__ import annotations

from datetime import timedelta
import logging

import defusedxml.ElementTree as ET
import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "OhmConnect Status"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OhmConnect sensor."""
    name = config.get(CONF_NAME)
    ohmid = config.get(CONF_ID)

    add_entities([OhmconnectSensor(name, ohmid)], True)


class OhmconnectSensor(SensorEntity):
    """Representation of a OhmConnect sensor."""

    def __init__(self, name, ohmid):
        """Initialize the sensor."""
        self._name = name
        self._ohmid = ohmid
        self._data = {}
        self._attr_unique_id = ohmid

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._data.get("active") == "True":
            return "Active"
        return "Inactive"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {"Address": self._data.get("address"), "ID": self._ohmid}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Get the latest data from OhmConnect."""
        try:
            url = f"https://login.ohmconnect.com/verify-ohm-hour/{self._ohmid}"
            response = requests.get(url, timeout=10)
            root = ET.fromstring(response.text)

            for child in root:
                self._data[child.tag] = child.text
        except requests.exceptions.ConnectionError:
            _LOGGER.error("No route to host/endpoint: %s", url)
            self._data = {}
