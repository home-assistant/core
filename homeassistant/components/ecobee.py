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
from homeassistant.loader import get_component
from homeassistant.util import Throttle

REQUIREMENTS = [
    'https://github.com/nkgilley/python-ecobee-api/archive/'
    '4856a704670c53afe1882178a89c209b5f98533d.zip#python-ecobee==0.0.6']

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
    configurator = get_component('configurator')
    if 'ecobee' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['ecobee'], "Failed to register, please try again.")

        return

    # pylint: disable=unused-argument
    def ecobee_configuration_callback(callback_data):
        """The actions to do when our configuration callback is called."""
        network.request_tokens()
        network.update()
        setup_ecobee(hass, network, config)

    _CONFIGURING['ecobee'] = configurator.request_config(
        hass, "Ecobee", ecobee_configuration_callback,
        description=(
            'Please authorize this app at https://www.ecobee.com/consumer'
            'portal/index.html with pin code: ' + network.pin),
        description_image="/static/images/config_ecobee_thermostat.png",
        submit_caption="I have authorized the app."
    )


def setup_ecobee(hass, network, config):
    """Setup Ecobee thermostat."""
    # If ecobee has a PIN then it needs to be configured.
    if network.pin is not None:
        request_configuration(network, hass, config)
        return

    if 'ecobee' in _CONFIGURING:
        configurator = get_component('configurator')
        configurator.request_done(_CONFIGURING.pop('ecobee'))

    hold_temp = config[DOMAIN].get(CONF_HOLD_TEMP)

    discovery.load_platform(hass, 'climate', DOMAIN,
                            {'hold_temp': hold_temp}, config)
    discovery.load_platform(hass, 'sensor', DOMAIN, {}, config)
    discovery.load_platform(hass, 'binary_sensor', DOMAIN, {}, config)


# pylint: disable=too-few-public-methods
class EcobeeData(object):
    """Get the latest data and update the states."""

    def __init__(self, config_file):
        """Initialize the Ecobee data object."""
        from pyecobee import Ecobee
        self.ecobee = Ecobee(config_file)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from pyecobee."""
        self.ecobee.update()
        _LOGGER.info("Ecobee data updated successfully")


def setup(hass, config):
    """Setup Ecobee.

    Will automatically load thermostat and sensor components to support
    devices discovered on the network.
    """
    # pylint: disable=global-statement, import-error
    global NETWORK

    if 'ecobee' in _CONFIGURING:
        return

    from pyecobee import config_from_file

    # Create ecobee.conf if it doesn't exist
    if not os.path.isfile(hass.config.path(ECOBEE_CONFIG_FILE)):
        jsonconfig = {"API_KEY": config[DOMAIN].get(CONF_API_KEY)}
        config_from_file(hass.config.path(ECOBEE_CONFIG_FILE), jsonconfig)

    NETWORK = EcobeeData(hass.config.path(ECOBEE_CONFIG_FILE))

    setup_ecobee(hass, NETWORK.ecobee, config)

    return True
