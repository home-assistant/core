"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

A minimal configuration.yaml is as as below:

evohome:
  username: !secret evohome_username
  password: !secret evohome_password

# This config parameter is presented with its default value:
# location_idx: 0        # if you have more than 1 location, use this index

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/evohome/
"""

# Glossary
# TCS - temperature control system (a.k.a. Controller, Parent), which can
# have up to 13 Children:
#   0-12 Heating zones (a.k.a. Zone), and
#   0-1 DHW controller, (a.k.a. Boiler)

import logging
from requests import RequestException
import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
    HTTP_BAD_REQUEST
)

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['evohomeclient==0.2.7']

_LOGGER = logging.getLogger(__name__)

# these are specific to this component
DOMAIN = 'evohome'
DATA_EVOHOME = 'data_' + DOMAIN
DISPATCHER_EVOHOME = 'dispatcher_' + DOMAIN

CONF_LOCATION_IDX = 'location_idx'
MAX_TEMP = 35
MIN_TEMP = 5
SCAN_INTERVAL_DEFAULT = 180
SCAN_INTERVAL_MAX = 300

# Validation of the user's configuration.
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


# bit masks for dispatcher packets
EVO_PARENT = 0x01
EVO_CHILD = 0x02

# these are used to help prevent E501 (line too long) violations
GWS = 'gateways'
TCS = 'temperatureControlSystems'


def setup(hass, config):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    One controller with 0+ heating zones (e.g. TRVs, relays) and, optionally, a
    DHW controller.  Does not work for US-based systems.
    """
    # Used for internal data, such as installation, state & timers...
    hass.data[DATA_EVOHOME] = {}

    domain_data = hass.data[DATA_EVOHOME]
    domain_data['timers'] = {}

    # Pull the configuration parameters...
    domain_data['params'] = dict(config[DOMAIN])
    # scan_interval - start with default value
    domain_data['params'][CONF_SCAN_INTERVAL] = SCAN_INTERVAL_DEFAULT

    if _LOGGER.isEnabledFor(logging.DEBUG):  # then redact username, password
        tmp = dict(domain_data['params'])
        tmp[CONF_USERNAME] = 'REDACTED'
        tmp[CONF_PASSWORD] = 'REDACTED'

        _LOGGER.debug("setup(): Configuration parameters: %s", tmp)

    from evohomeclient2 import EvohomeClient

    _LOGGER.debug("setup(): API call [4 request(s)]: client.__init__()...")

    try:
        # there's a bug in evohomeclient2 v0.2.7: the client.__init__() sets
        # the root loglevel (debug=?), so must remember it now...
        log_level = logging.getLogger().getEffectiveLevel()

        client = EvohomeClient(
            domain_data['params'][CONF_USERNAME],
            domain_data['params'][CONF_PASSWORD],
            debug=False
        )
        # ...then restore it to what it was before instantiating the client
        logging.getLogger().setLevel(log_level)

    except RequestException as err:
        if str(HTTP_BAD_REQUEST) in str(err):
            # this happens when bad user credentials are supplied
            _LOGGER.error(
                "Failed to establish a connection with evohome web servers, "
                "Check your username (%s), and password are correct."
                "Unable to continue. Resolve any errors and restart HA.",
                domain_data['params'][CONF_USERNAME]
            )
        else:
            # Otherwise, it may be enough to back off and try again later.
            raise PlatformNotReady(err)

    finally:  # Redact username, password as no longer needed.
        domain_data['params'][CONF_USERNAME] = 'REDACTED'
        domain_data['params'][CONF_PASSWORD] = 'REDACTED'

    domain_data['client'] = client

    # Redact any installation data we'll never need.
    if client.installation_info[0]['locationInfo']['locationId'] != 'REDACTED':
        for loc in client.installation_info:
            loc['locationInfo']['locationId'] = 'REDACTED'
            loc['locationInfo']['streetAddress'] = 'REDACTED'
            loc['locationInfo']['city'] = 'REDACTED'
            loc['locationInfo']['locationOwner'] = 'REDACTED'
            loc[GWS][0]['gatewayInfo'] = 'REDACTED'

    # Pull down the installation configuration...
    loc_idx = domain_data['params'][CONF_LOCATION_IDX]

    try:
        domain_data['config'] = client.installation_info[loc_idx]

    # IndexError: configured location index is outside the range
    except IndexError:
        _LOGGER.warning(
            "setup(): Config parameter, '%s'= %s , is out of range (0-%s)",
            CONF_LOCATION_IDX,
            loc_idx,
            len(client.installation_info) - 1
        )

        raise

    domain_data['status'] = {}

    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "setup(): Location/TCS (temp. control system) used is: %s [%s]",
            domain_data['config'][GWS][0][TCS][0]['systemId'],
            domain_data['config']['locationInfo']['name']
        )
        # Some platform data needs further redaction before being logged.
        tmp = dict(domain_data['config'])
        tmp['locationInfo']['postcode'] = 'REDACTED'

        _LOGGER.debug("setup(): domain_data['config']: %s", tmp)

    # We have the platofrom configuration, but no state as yet, so...
    def _first_update(event):
        """Let the controller know it can obtain it's first update."""
    # Send a message to the hub to do its first update()
        pkt = {
            'sender': 'setup()',
            'signal': 'update',
            'to': EVO_PARENT
        }
        hass.helpers.dispatcher.dispatcher_send(
            DISPATCHER_EVOHOME,
            pkt
        )

    hass.bus.listen(EVENT_HOMEASSISTANT_START, _first_update)

    load_platform(hass, 'climate', DOMAIN)

    return True
