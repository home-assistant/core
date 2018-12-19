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


# Available pump ids with assigned HA names
# Available as switches
AVAILABLE_PUMPS = {
    "central_heating_pump": "Central heating pump",
    "central_heating_pump2": "Central heating pump2",
    "domestic_hot_water_pump": "Central hot water pump",
}

# Available temp sensor ids with assigned HA names
# Available as sensors
AVAILABLE_SENSORS = {
    "outdoor_temp": 'Outdoor temperature',
    "indoor_temp": 'Indoor temperature',
    "indoor2_temp": 'Indoor temperature 2',
    "domestic_hot_water_temp": 'Domestic hot water temperature',
    "target_domestic_hot_water_temp": 'Target hot water temperature',
    "feedwater_in_temp": 'Feedwater input temperature',
    "feedwater_out_temp": 'Feedwater output temperature',
    "target_feedwater_temp": 'Target feedwater temperature',
    "fuel_feeder_temp": 'Fuel feeder temperature',
    "exhaust_temp": 'Exhaust temperature',
}


CONF_SWITCHES = 'switches'
SWITCHES_SCHEMA = []
for pump_id in AVAILABLE_PUMPS.keys():
    SWITCHES_SCHEMA.append(vol.Optional(pump_id))

CONF_SENSORS = 'sensors'
SENSORS_SCHEMA = []
for tempsensor_id in AVAILABLE_SENSORS.keys():
    SENSORS_SCHEMA.append(vol.Optional(tempsensor_id))

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
