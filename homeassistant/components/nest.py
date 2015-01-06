"""
homeassistant.components.nest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with Nest Thermostats.
"""
import logging
import homeassistant.util as util
from homeassistant.helpers import validate_config, ToggleDevice
from homeassistant.const import (ATTR_ENTITY_PICTURE, ATTR_UNIT_OF_MEASUREMENT,
                                 ATTR_FRIENDLY_NAME, STATE_ON, SERVICE_TURN_ON, SERVICE_TURN_OFF, ATTR_ENTITY_ID,
                                 ATTR_NEW_TARGET_TEMPERATURE, SERVICE_SET_TARGET_TEMPERATURE)
from datetime import datetime, timedelta

# The domain of your component. Should be equal to the name of your component
DOMAIN = "nest"
ENTITY_AWAY_NAME = "state away"
ENTITY_TEMP_INSIDE_ID = "nest_get.temperature_inside"
ENTITY_TEMP_TARGET_ID = "nest_get.temperature_target"
ENTITY_TEMP_TARGET_SET = "nest_set.temperature_target"

ENTITY_AWAY_ID_FORMAT = DOMAIN + '.{}'

# Configuration key for the entity id we are targeting
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = []

def is_on(hass, entity_id=None):

    return hass.states.is_state(entity_id, STATE_ON)


def turn_on(hass, entity_id=None):
    """ Turns all or specified switch on. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_ON, data)


def turn_off(hass, entity_id=None):
    """ Turns all or specified switch off. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else None

    hass.services.call(DOMAIN, SERVICE_TURN_OFF, data)

def set_temperature(hass, entity_id=None, new_temp=None):
    """ Set new target temperature. """
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    if new_temp:
        data[ATTR_NEW_TARGET_TEMPERATURE] = new_temp

    hass.services.call(DOMAIN, SERVICE_SET_TARGET_TEMPERATURE, data)

def setup(hass, config):
    """ Setup NEST thermostat. """

    # Validate that all required config options are given
    if not validate_config(config, {DOMAIN: [CONF_USERNAME, CONF_PASSWORD]}, _LOGGER):
        return False

    try:
        import homeassistant.external.pynest.nest as pynest
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pynest. "))
        return False

    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    thermostat = NestThermostat(pynest.Nest(username, password, None))
    thermostat.entity_id = ENTITY_AWAY_ID_FORMAT.format(util.slugify(ENTITY_AWAY_NAME))
    thermostat.nest.login()

    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_nest_state(now):
        """ Update nest state. """

        logging.getLogger(__name__).info("Update nest state")

        thermostat.nest.get_status()
        thermostat.update_ha_state(hass)

    # Update state every 30 seconds
    hass.track_time_change(update_nest_state, second=[0])
    update_nest_state(None)

    def handle_nest_service(service):
        """ Handles calls to the nest services. """
        if service.service == SERVICE_TURN_ON:
            thermostat.turn_on()
        else:
            thermostat.turn_off()

        thermostat.nest.get_status()
        thermostat.update_ha_state(hass)

    hass.services.register(DOMAIN, SERVICE_TURN_OFF, handle_nest_service)
    hass.services.register(DOMAIN, SERVICE_TURN_ON, handle_nest_service)

    def handle_nest_set_temperature(service):
        if service.data[ATTR_NEW_TARGET_TEMPERATURE]:
            new_temp = float(service.data[ATTR_NEW_TARGET_TEMPERATURE])
            thermostat.nest.set_temperature(new_temp)
            thermostat.nest.get_status()
            nest_temp(datetime.now())

    hass.services.register(DOMAIN, SERVICE_SET_TARGET_TEMPERATURE, handle_nest_set_temperature)

    def nest_temp(time):
        """ Method to get the current inside and target temperatures. """

        #thermostat.nest.get_status()
        current_temperature = thermostat.nest.get_curtemp()
        target_temperature = thermostat.nest.get_tartemp()


        hass.states.set(ENTITY_TEMP_INSIDE_ID, current_temperature, {ATTR_UNIT_OF_MEASUREMENT: thermostat.nest.get_units(), ATTR_ENTITY_PICTURE:
                     "https://cdn2.iconfinder.com/data/icons/windows-8-metro-ui-weather-report/512/Temperature.png"})

        hass.states.set(ENTITY_TEMP_TARGET_ID, target_temperature, {ATTR_UNIT_OF_MEASUREMENT: thermostat.nest.get_units(), ATTR_ENTITY_PICTURE:
                     "http://d1hwvnnkb0v1bo.cloudfront.net/content/art/app/icons/target_icon.jpg"})

    hass.track_time_change(nest_temp, second=[10])
    nest_temp(datetime.now())

    # Tells the bootstrapper that the component was succesfully initialized
    return True

class NestThermostat(ToggleDevice):


    def __init__(self, nest):
        self.nest = nest
        self.state_attr = {ATTR_FRIENDLY_NAME: ENTITY_AWAY_NAME, ATTR_ENTITY_PICTURE:
                     "http://support-assets.nest.com/images/tpzimages/app-energy-history-basic-away-icon.png"}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return ENTITY_AWAY_NAME

    def turn_on(self, **kwargs):
        """ Turns away on. """
        self.nest.set_away("away")

    def turn_off(self):
        """ Turns away off. """
        self.nest.set_away("here")

    def is_on(self):
        """ True if away is on. """
        return self.nest.is_away()

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

    def set_temperature(self, temperature):
        """ Set new target temperature """
        self.nest.set_temperature(temperature)

