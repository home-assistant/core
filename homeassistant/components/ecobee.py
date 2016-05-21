"""
Support for Ecobee.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ecobee/
"""
import logging
import os
from datetime import timedelta

from homeassistant import bootstrap
from homeassistant.const import (
    ATTR_DISCOVERED, ATTR_SERVICE, CONF_API_KEY, EVENT_PLATFORM_DISCOVERED)
from homeassistant.loader import get_component
from homeassistant.util import Throttle

DOMAIN = "ecobee"
DISCOVER_THERMOSTAT = "ecobee.thermostat"
DISCOVER_SENSORS = "ecobee.sensor"
NETWORK = None
HOLD_TEMP = 'hold_temp'

REQUIREMENTS = [
    'https://github.com/nkgilley/python-ecobee-api/archive/'
    '4a884bc146a93991b4210f868f3d6aecf0a181e6.zip#python-ecobee==0.0.5']

_LOGGER = logging.getLogger(__name__)

ECOBEE_CONFIG_FILE = 'ecobee.conf'
_CONFIGURING = {}

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)


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

    # Ensure component is loaded
    bootstrap.setup_component(hass, 'thermostat', config)
    bootstrap.setup_component(hass, 'sensor', config)

    hold_temp = config[DOMAIN].get(HOLD_TEMP, False)

    # Fire thermostat discovery event
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_THERMOSTAT,
        ATTR_DISCOVERED: {'hold_temp': hold_temp}
    })

    # Fire sensor discovery event
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_SENSORS,
        ATTR_DISCOVERED: {}
    })


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
        _LOGGER.info("ecobee data updated successfully.")


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
        if config[DOMAIN].get(CONF_API_KEY) is None:
            _LOGGER.error("No ecobee api_key found in config.")
            return
        jsonconfig = {"API_KEY": config[DOMAIN].get(CONF_API_KEY)}
        config_from_file(hass.config.path(ECOBEE_CONFIG_FILE), jsonconfig)

    NETWORK = EcobeeData(hass.config.path(ECOBEE_CONFIG_FILE))

    setup_ecobee(hass, NETWORK.ecobee, config)

    return True
