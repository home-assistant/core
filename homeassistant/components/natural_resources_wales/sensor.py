"""Platform for natural resources wales sensor."""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.components.natural_resources_wales.river_levels_sensor as rls
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_NAME = "Natural Resources Wales"
DEFAULT_LANGUAGE = "en"
CONF_LANGUAGE = "language"
LANGUAGE_CODES = [
    "en",
    "cy",
]
CONF_MONITORED_STATIONS = "monitored_stations"


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): vol.In(LANGUAGE_CODES),
        vol.Optional(CONF_MONITORED_STATIONS, default=[]): vol.All(
            cv.ensure_list, [str]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    language = config.get(CONF_LANGUAGE)
    interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)

    river_levels = rls.NaturalResourcesWalesRiverLevelsComponent(
        river_levels_api_key=config.get(CONF_API_KEY, None),
        language=language.upper(),
        interval=interval,
        monitored=config.get(CONF_MONITORED_STATIONS),
    )

    add_entities(river_levels.get_sensors(), True)
