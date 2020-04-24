"""Platform for natural resources wales sensor."""
from datetime import timedelta
import logging

import voluptuous as vol

import homeassistant.components.natural_resources_wales.river_levels_sensor as rls
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL
import homeassistant.helpers.config_validation as cv

SCAN_INTERVAL = timedelta(seconds=35)
DEFAULT_NAME = "Natural Resources Wales"
DEFAULT_LANGUAGE = "en"
CONF_LANGUAGE = "language"
LANGUAGE_CODES = [
    "en",
    "cy",
]
CONF_MONITORED_STATIONS = "monitored_stations"
CONF_RIVER_LEVELS_KEY = "river_levels_key"
CONF_FLOOD_RISK_FORECAST_KEY = "flood_risk_forecast_key"
CONF_LIVE_FLOOD_WARNINGS_KEY = "live_flood_warnings_key"


_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_RIVER_LEVELS_KEY): cv.string,
        vol.Optional(CONF_FLOOD_RISK_FORECAST_KEY): cv.string,
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

    river_levels_key = config.get(CONF_RIVER_LEVELS_KEY, None)
    flood_risk_forecast_key = config.get(CONF_FLOOD_RISK_FORECAST_KEY, None)
    live_flood_warnings_key = config.get(CONF_LIVE_FLOOD_WARNINGS_KEY, None)

    if river_levels_key is not None:
        print("RIVER LEVELS KEY SET", river_levels_key)
    if flood_risk_forecast_key is not None:
        print("FLOOD RISK FORECAST KEY SET", flood_risk_forecast_key)
    if live_flood_warnings_key is not None:
        print("LIVE FLOOD WARNINGS KEY SET", live_flood_warnings_key)

    river_levels = rls.NaturalResourcesWalesRiverLevelsComponent(
        river_levels_key=config.get(CONF_RIVER_LEVELS_KEY, None),
        language=language.upper(),
        interval=interval,
        monitored=config.get(CONF_MONITORED_STATIONS),
    )

    add_entities(river_levels.get_sensors(), True)
