"""Support for OpenERZ API for Zurich city waste disposal system."""
from datetime import timedelta
import logging

from openerz_api.main import OpenERZConnector
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
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


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    openerz_config = {
        "zip": config[CONF_ZIP],
        "waste_type": config[CONF_WASTE_TYPE],
        "name": config.get(CONF_NAME),
    }
    add_entities([OpenERZSensor(openerz_config)])


class OpenERZSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, openerz_config):
        """Initialize the sensor."""
        self._state = None
        self.openerz_config = openerz_config
        self.zip = self.openerz_config["zip"]
        self.waste_type = self.openerz_config["waste_type"]
        self.friendly_name = self.openerz_config.get("name", self.waste_type)
        self.api_connector = OpenERZConnector(self.zip, self.waste_type)

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""

        return self.friendly_name

    @property
    def state(self):
        """Return the state of the sensor."""

        return self._state

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """

        self._state = self.api_connector.find_next_pickup(day_offset=31)
