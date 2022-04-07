"""Support for OpenERZ API for Zurich city waste disposal system."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from openerz_api.main import OpenERZConnector
import voluptuous as vol

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
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

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return SensorDeviceClass.TIMESTAMP

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.

        The api returns a string of format "%Y-%m-%d". From the ERZ website,
        it can be deducted that the pickup happens after 07:00 in the morning.

        As this platform only works for Zurich, the timezone will be set to Zurich.
        """
        date_string = self.api_connector.find_next_pickup(day_offset=31)
        time_string = "07:00"
        datetime_string = f"{date_string} {time_string}"
        zh_tz = ZoneInfo("Europe/Zurich")
        self._state = datetime.strptime(datetime_string, "%Y-%m-%d %H:%M").replace(
            tzinfo=zh_tz
        )
