"""Support for OpenERZ API for Zurich city waste disposal system."""
from __future__ import annotations

from datetime import timedelta

from openerz_api.main import OpenERZConnector
import voluptuous as vol

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

SCAN_INTERVAL = timedelta(hours=12)

CONF_ZIP = "zip"
CONF_WASTE_TYPE = "waste_type"
CONF_NAME = "name"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ZIP): cv.positive_int,
        vol.Required(CONF_WASTE_TYPE, default="waste"): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    api_connector = OpenERZConnector(config[CONF_ZIP], config[CONF_WASTE_TYPE])
    add_entities([OpenERZSensor(api_connector, config.get(CONF_NAME))], True)


class OpenERZSensor(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, api_connector, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self.api_connector = api_connector

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = self.api_connector.find_next_pickup(day_offset=31)
