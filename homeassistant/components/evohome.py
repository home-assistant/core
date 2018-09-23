"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.evohome/
"""

# Glossary:
# TCS - temperature control system (a.k.a. Controller, Parent), which can
# have up to 13 Children:
#   0-12 Heating zones (a.k.a. Zone), and
#   0-1 DHW controller, (a.k.a. Boiler)

import logging
import requests
import voluptuous as vol

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    HTTP_BAD_REQUEST
)

from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform

REQUIREMENTS = ['evohomeclient==0.2.7']
# If ever > 0.2.7, re-check the work-around wrapper is still required when
# instantiating the client, below.

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'evohome'
DATA_EVOHOME = 'data_' + DOMAIN

CONF_LOCATION_IDX = 'location_idx'
MAX_TEMP = 35
MIN_TEMP = 5
SCAN_INTERVAL_DEFAULT = 180
SCAN_INTERVAL_MAX = 300

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)

# These are used to help prevent E501 (line too long) violations.
GWS = 'gateways'
TCS = 'temperatureControlSystems'


def setup(hass, config):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    One controller with 0+ heating zones (e.g. TRVs, relays) and, optionally, a
    DHW controller.  Does not work for US-based systems.
    """
    domain_data = hass.data[DATA_EVOHOME] = {}
    domain_data['timers'] = {}

    domain_data['params'] = dict(config[DOMAIN])
    domain_data['params'][CONF_SCAN_INTERVAL] = SCAN_INTERVAL_DEFAULT

    from evohomeclient2 import EvohomeClient

    _LOGGER.debug("setup(): API call [4 request(s)]: client.__init__()...")

    try:
        # There's a bug in evohomeclient2 v0.2.7: the client.__init__() sets
        # the root loglevel when EvohomeClient(debug=?), so remember it now...
        log_level = logging.getLogger().getEffectiveLevel()

        client = EvohomeClient(
            domain_data['params'][CONF_USERNAME],
            domain_data['params'][CONF_PASSWORD],
            debug=False
        )
        # ...then restore it to what it was before instantiating the client
        logging.getLogger().setLevel(log_level)

    except requests.exceptions.HTTPError as err:
        if err.response.status_code == HTTP_BAD_REQUEST:
            _LOGGER.error(
                "Failed to establish a connection with evohome web servers, "
                "Check your username (%s), and password are correct."
                "Unable to continue. Resolve any errors and restart HA.",
                domain_data['params'][CONF_USERNAME]
            )
            return False  # unable to continue

        raise PlatformNotReady(err)

    except requests.RequestException as err:
        raise PlatformNotReady(err)

    else:  # Redact username, password as no longer needed.
        domain_data['params'][CONF_USERNAME] = 'REDACTED'
        domain_data['params'][CONF_PASSWORD] = 'REDACTED'

    domain_data['client'] = client

    # Redact any installation data we'll never need.
    if client.installation_info[0]['locationInfo']['locationId'] != 'REDACTED':
        for loc in client.installation_info:
            loc['locationInfo']['streetAddress'] = 'REDACTED'
            loc['locationInfo']['city'] = 'REDACTED'
            loc['locationInfo']['locationOwner'] = 'REDACTED'
            loc[GWS][0]['gatewayInfo'] = 'REDACTED'

    # Pull down the installation configuration.
    loc_idx = domain_data['params'][CONF_LOCATION_IDX]

    try:
        domain_data['config'] = client.installation_info[loc_idx]

    except IndexError:
        _LOGGER.warning(
            "setup(): Parameter '%s' = %s , is outside its range (0-%s)",
            CONF_LOCATION_IDX,
            loc_idx,
            len(client.installation_info) - 1
        )

        return False  # unable to continue

    domain_data['status'] = {}

    _LOGGER.debug(
        "setup(): The location (temperature control system) "
        "used is: %s [%s] (%s [%s])",
        domain_data['config']['locationInfo']['locationId'],
        domain_data['config']['locationInfo']['name'],
        domain_data['config'][GWS][0][TCS][0]['systemId'],
        domain_data['config'][GWS][0][TCS][0]['modelType']
    )

    load_platform(hass, 'climate', DOMAIN)

    return True
