"""
Adds support for the essent icy e-thermostaat units.
For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.e_thermostaat/
"""
import logging

import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

URL_LOGIN = "https://portal.icy.nl/login"
URL_DATA = "https://portal.icy.nl/data"

DEFAULT_NAME = 'E-Thermostaat'

CONF_NAME = 'name'
CONF_TARGET_TEMP = 'target_temp'
CONF_AWAY_TEMPERATURE = 'away_temperature'
CONF_COMFORT_TEMPERATURE = 'comfort_temperature'

DEFAULT_AWAY_TEMPERATURE = 14
DEFAULT_COMFORT_TEMPERATURE = 19

# Values reverse engineered
HOME = 32
AWAY = 64

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_AWAY_TEMPERATURE, default=DEFAULT_AWAY_TEMPERATURE):
        vol.Coerce(float),
    vol.Optional(CONF_COMFORT_TEMPERATURE,
                 default=DEFAULT_COMFORT_TEMPERATURE): vol.Coerce(float),
    vol.Optional(CONF_TARGET_TEMP): vol.Coerce(float),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    import requests
    """Setup the e thermostat."""
    name = config.get(CONF_NAME)
    target_temp = config.get(CONF_TARGET_TEMP)
    away_temp = config.get(CONF_AWAY_TEMPERATURE)
    comfort_temp = config.get(CONF_COMFORT_TEMPERATURE)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    add_devices([EThermostaat(
        name, username, password, away_temp, comfort_temp,
        target_temp)])


class EThermostaat(ClimateDevice):
    """Representation of a EThermostaat device."""

    def __init__(self, name, username, password,
                 away_temp, comfort_temp, target_temp):
        """Initialize the thermostat."""
        self._name = name
        self._username = username
        self._password = password
        self._comfort_temp = comfort_temp
        self._away = False
        self._away_temp = away_temp
        self._current_temperature = None
        self._target_temperature = target_temp
        self._old_conf = None
        self.update()

    @property
    def name(self):
        """Return the name of the honeywell, if any."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._set_temperature(temperature)

    def _set_temperature(self, temperature, home=True):
        """Set new target temperature, via URL commands"""
        token, uid = self.get_token_and_uid()
        header = {'Session-token': token}

        payload_new = [("uid", uid),
                       ("temperature1", temperature)]

        if self._old_conf is not None:
            if home:
                payload_new.append(("configuration[]", HOME))
            else:
                payload_new.append(("configuration[]", AWAY))
            for i in self._old_conf[1:]:
                payload_new.append(('configuration[]', i))
        r = requests.post(URL_DATA, data=payload_new, headers=header)
        try:
            if not r.json()['status']['code'] == 200:
                _LOGGER.error("Could not set temperature")
        except Exception as e:
            _LOGGER.error(e)
            return

    def get_token_and_uid(self):
        """Get the Session Token and UID of the Thermostaat"""
        payload = {'username': self._username, 'password': self._password}

        with requests.Session() as s:
            s.get(URL_LOGIN)
            r = s.post(URL_LOGIN, data=payload)
            try:
                res = r.json()
                token = res['token']
                uid = res['serialthermostat1']
            except Exception as e:
                _LOGGER.error("Could not get token and uid: %s" % e)
                return None, None
        return token, uid

    def _get_data(self):
        """Get the data  of the Thermostaat"""
        token, uid = self.get_token_and_uid()

        header = {'Session-token': token}
        payload = {'username': self._username, 'password': self._password}

        r = requests.get(URL_DATA, data=payload, headers=header)
        try:
            data = r.json()

            self._target_temperature = data['temperature1']
            self._current_temperature = data['temperature2']

            self._old_conf = data['configuration']

            if self._old_conf[0] >= AWAY:
                self._away = True
            else:
                self._away = False
        except Exception as e:
            _LOGGER.error("Could not get data from e-Thermostaat: %s" % e)

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._away

    def turn_away_mode_on(self):
        """Turn away on."""
        self._away = True
        self._set_temperature(self._away_temp, home=False)

    def turn_away_mode_off(self):
        """Turn away off and set comfort temp."""
        self._away = False
        self._set_temperature(self._comfort_temp, home=True)

    def update(self):
        """Get the latest data."""
        self._get_data()

