"""
homeassistant.components.zwave
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Connects Home Assistant to the Ecobee API and maintains tokens.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/ecobee/

[ecobee]
api_key: asdflaksf
"""

from homeassistant.loader import get_component
from homeassistant import bootstrap
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE, ATTR_DISCOVERED, CONF_API_KEY)
from datetime import timedelta
import logging
import os

DOMAIN = "ecobee"
DISCOVER_THERMOSTAT = "ecobee.thermostat"
DEPENDENCIES = []
NETWORK = None

REQUIREMENTS = [
    'https://github.com/nkgilley/python-ecobee-api/archive/'
    'd35596b67c75451fa47001c493a15eebee195e93.zip#python-ecobee==0.0.1']

_LOGGER = logging.getLogger(__name__)

ECOBEE_CONFIG_FILE = 'ecobee.conf'
_CONFIGURING = {}

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)


def request_configuration(network, hass):
    """ Request configuration steps from the user. """
    configurator = get_component('configurator')
    if 'ecobee' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['ecobee'], "Failed to register, please try again.")

        return

    # pylint: disable=unused-argument
    def ecobee_configuration_callback(callback_data):
        """ Actions to do when our configuration callback is called. """
        network.request_tokens()
        network.update()
        setup_ecobee(hass, network)

    _CONFIGURING['ecobee'] = configurator.request_config(
        hass, "Ecobee", ecobee_configuration_callback,
        description=(
            'Please authorize this app at https://www.ecobee.com/consumer'
            'portal/index.html with pin code: ' + NETWORK.pin),
        description_image="/static/images/config_ecobee_thermostat.png",
        submit_caption="I have authorized the app."
    )


def setup_ecobee(hass, network):
    """ Setup ecobee thermostat """
    # If ecobee has a PIN then it needs to be configured.
    if network.pin is not None:
        request_configuration(network, hass)
        return

    if 'ecobee' in _CONFIGURING:
        configurator = get_component('configurator')
        configurator.request_done(_CONFIGURING.pop('ecobee'))


def setup(hass, config):
    """
    Setup Ecobee.
    Will automatically load thermostat and sensor components to support
    devices discovered on the network.
    """
    # pylint: disable=global-statement, import-error
    global NETWORK

    if 'ecobee' in _CONFIGURING:
        return

    from pyecobee import Ecobee, config_from_file

    # Create ecobee.conf if it doesn't exist
    if not os.path.isfile(hass.config.path(ECOBEE_CONFIG_FILE)):
        if config[DOMAIN].get(CONF_API_KEY) is None:
            _LOGGER.error("No ecobee api_key found in config.")
            return
        jsonconfig = {"API_KEY": config[DOMAIN].get(CONF_API_KEY)}
        config_from_file(hass.config.path(ECOBEE_CONFIG_FILE), jsonconfig)

    NETWORK = Ecobee(hass.config.path(ECOBEE_CONFIG_FILE))

    setup_ecobee(hass, NETWORK)

    # Ensure component is loaded
    bootstrap.setup_component(hass, 'thermostat', config)

    # Fire discovery event
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: DISCOVER_THERMOSTAT,
        ATTR_DISCOVERED: {
            'network': NETWORK,
        }
    })

    def stop_ecobee(event):
        """ Stop Ecobee. """

        pass

    def start_ecobee(event):
        """ Called when Home Assistant starts up. """

        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_ecobee)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_ecobee)

    return True
