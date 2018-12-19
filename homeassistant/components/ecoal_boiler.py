"""
Component to control ecoal/esterownik.pl coal/wood boiler controller.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ecoal_boiler/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['ecoaliface==0.4.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecoal_boiler"
DATA_ECOAL_BOILER = 'data_' + DOMAIN

DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"


# Available pump ids
# Available as switches
PUMP_IDNAMES = (
    "central_heating_pump",
    "domestic_hot_water_pump",
    "central_heating_pump2",
)

# Available temp sensor ids
# Available as sensors
SENSOR_IDS = (
    "outdoor_temp",
    "indoor_temp",
    "indoor2_temp",
    "domestic_hot_water_temp",
    "target_domestic_hot_water_temp",
    "feedwater_in_temp",
    "feedwater_out_temp",
    "target_feedwater_temp",
    "coal_feeder_temp",
    "exhaust_temp",
)


CONF_SWITCHES = 'switches'
SWITCHES_SCHEMA = {}
for pump_id in PUMP_IDNAMES:
    SWITCHES_SCHEMA[vol.Optional(pump_id)] = cv.string

CONF_SENSORS = 'sensors'
SENSORS_SCHEMA = {}
for tempsensor_id in SENSOR_IDS:
    SENSORS_SCHEMA[vol.Optional(tempsensor_id)] = cv.string

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_USERNAME,
                     default=DEFAULT_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD,
                     default=DEFAULT_PASSWORD): cv.string,
        vol.Optional(CONF_SWITCHES): SWITCHES_SCHEMA,
        vol.Optional(CONF_SENSORS): SENSORS_SCHEMA,
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, hass_config):
    """Set up global ECoalController instance same for sensors and switches."""
    from ecoaliface.simple import ECoalController

    conf = hass_config[DOMAIN]
    host = conf[CONF_HOST]
    username = conf[CONF_USERNAME]
    passwd = conf[CONF_PASSWORD]
    ecoal_contr = ECoalController(host, username, passwd)
    if ecoal_contr.version is None:
        # Wrong credentials nor network config
        return False
    _LOGGER.debug("Detected controller version: %r @%s",
                  ecoal_contr.version, host, )
    # Creating ECoalController instance makes HTTP request to controller.
    hass.data[DATA_ECOAL_BOILER] = ecoal_contr
    # Setup switches
    switches = conf.get(CONF_SWITCHES)
    if switches:
        load_platform(hass, 'switch', DOMAIN, switches, hass_config)
    # Setup temp sensors
    sensors = conf.get(CONF_SENSORS)
    if sensors:
        load_platform(hass, 'sensor', DOMAIN, sensors, hass_config)
    return True
