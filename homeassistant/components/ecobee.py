"""
Support for Ecobee.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ecobee/
"""
import logging
import os
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.const import CONF_API_KEY
from homeassistant.util import Throttle
from homeassistant.util.json import save_json

REQUIREMENTS = ['python-ecobee-api==0.0.18']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

CONF_HOLD_TEMP = 'hold_temp'

DOMAIN = 'ecobee'

ECOBEE_CONFIG_FILE = 'ecobee.conf'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)

NETWORK = None

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_API_KEY): cv.string,
        vol.Optional(CONF_HOLD_TEMP, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


def request_configuration(network, hass, config):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator
    if 'ecobee' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['ecobee'], "Failed to register, please try again.")

        return

    def ecobee_configuration_callback(callback_data):
        """Handle configuration callbacks."""
        network.request_tokens()
        network.update()
        setup_ecobee(hass, network, config)

    _CONFIGURING['ecobee'] = configurator.request_config(
        "Ecobee", ecobee_configuration_callback,
        description=(
            'Please authorize this app at https://www.ecobee.com/consumer'
            'portal/index.html with pin code: ' + network.pin),
        description_image="/static/images/config_ecobee_thermostat.png",
        submit_caption="I have authorized the app."
    )


def setup_ecobee(hass, network, config):
    """Set up the Ecobee thermostat."""
    # If ecobee has a PIN then it needs to be configured.
    if network.pin is not None:
        request_configuration(network, hass, config)
        return

    if 'ecobee' in _CONFIGURING:
        configurator = hass.components.configurator
        configurator.request_done(_CONFIGURING.pop('ecobee'))

    hold_temp = config[DOMAIN].get(CONF_HOLD_TEMP)

    discovery.load_platform(
        hass, 'climate', DOMAIN, {'hold_temp': hold_temp}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'weather', DOMAIN, {}, config)


class EcobeeData(object):
    """Get the latest data and update the states."""

    def __init__(self, config_file):
        """Init the Ecobee data object."""
        from pyecobee import Ecobee
        self.ecobee = Ecobee(config_file)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from pyecobee."""
        self.ecobee.update()
        _LOGGER.info("Ecobee data updated successfully")


def setup(hass, config):
    """Set up the Ecobee.

    Will automatically load thermostat and sensor components to support
    devices discovered on the network.
    """
    global NETWORK

    if 'ecobee' in _CONFIGURING:
        return

    # Create ecobee.conf if it doesn't exist
    if not os.path.isfile(hass.config.path(ECOBEE_CONFIG_FILE)):
        jsonconfig = {"API_KEY": config[DOMAIN].get(CONF_API_KEY)}
        save_json(hass.config.path(ECOBEE_CONFIG_FILE), jsonconfig)

    NETWORK = EcobeeData(hass.config.path(ECOBEE_CONFIG_FILE))

    setup_ecobee(hass, NETWORK.ecobee, config)

    return True
