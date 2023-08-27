"""Support to control ecoal/esterownik.pl coal/wood boiler controller."""
import logging

from ecoaliface.simple import ECoalController
import voluptuous as vol

from homeassistant.const import (
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_SENSORS,
    CONF_SWITCHES,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecoal_boiler"
DATA_ECOAL_BOILER = f"data_{DOMAIN}"

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


# Available pump ids with assigned HA names
# Available as switches
AVAILABLE_PUMPS = {
    "central_heating_pump": "Central heating pump",
    "central_heating_pump2": "Central heating pump2",
    "domestic_hot_water_pump": "Domestic hot water pump",
}

# available temp sensor ids with assigned ha names
TEMP_SENSORS = {
    "outdoor_temp": "Outdoor temperature",
    "indoor_temp": "Indoor temperature",
    "indoor2_temp": "Indoor temperature 2",
    "domestic_hot_water_temp": "Domestic hot water temperature",
    "target_domestic_hot_water_temp": "Target hot water temperature",
    "feedwater_in_temp": "Feedwater input temperature",
    "feedwater_out_temp": "Feedwater output temperature",
    "target_feedwater_temp": "Target feedwater temperature",
    "fuel_feeder_temp": "Fuel feeder temperature",
    "exhaust_temp": "Exhaust temperature",
    }


# Available percentage sensors
PERCENTAGE_SENSORS = {
    "fuel_left_percentage": "How many percent of fuel is left",
}

# Available sensor ids with assigned HA names
AVAILABLE_SENSORS = TEMP_SENSORS | PERCENTAGE_SENSORS

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(AVAILABLE_PUMPS)): vol.All(
            cv.ensure_list, [vol.In(AVAILABLE_PUMPS)]
        )
    }
)

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_MONITORED_CONDITIONS, default=list(AVAILABLE_SENSORS)
        ): vol.All(cv.ensure_list, [vol.In(AVAILABLE_SENSORS)])
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
                vol.Optional(CONF_SENSORS, default={}): SENSOR_SCHEMA,
                vol.Optional(CONF_SWITCHES, default={}): SWITCH_SCHEMA,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up global ECoalController instance same for sensors and switches."""

    conf = hass_config[DOMAIN]
    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    passwd = conf[CONF_PASSWORD]
    # Creating ECoalController instance makes HTTP request to controller.
    ecoal_contr = ECoalController(host, username, passwd)
    if ecoal_contr.version is None:
        # Wrong credentials nor network config
        _LOGGER.error(
            "Unable to read controller status from %s@%s (wrong host/credentials)",
            username,
            host,
        )
        return False
    _LOGGER.debug("Detected controller version: %r @%s", ecoal_contr.version, host)
    hass.data[DATA_ECOAL_BOILER] = ecoal_contr
    # Setup switches
    switches = conf[CONF_SWITCHES][CONF_MONITORED_CONDITIONS]
    load_platform(hass, Platform.SWITCH, DOMAIN, switches, hass_config)
    # Setup temp sensors
    sensors = conf[CONF_SENSORS][CONF_MONITORED_CONDITIONS]
    load_platform(hass, Platform.SENSOR, DOMAIN, sensors, hass_config)
    return True
