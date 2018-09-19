"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

A minimal configuration.yaml is as as below:

evohome:
  username: !secret evohome_username
  password: !secret evohome_password

These config parameters are presented with their default values:

# scan_interval: 180     # seconds, you can probably get away with 60
# location_idx: 0        # if you have more than 1 location, use this

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/evohome/
"""

# Glossary
# TCS - temperature control system (a.k.a. Controller, Master), which can
# have up to 13 Slaves:
#   0-12 Heating zones (a.k.a. Zone), and
#   0-1 DHW controller, (a.k.a. Boiler)

import logging
from datetime import datetime, timedelta
import requests
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice,

    SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE,
)

from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,

    EVENT_HOMEASSISTANT_START,
    PRECISION_TENTHS,

    TEMP_CELSIUS,

    HTTP_BAD_REQUEST,
    HTTP_TOO_MANY_REQUESTS,
)

from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['evohomeclient==0.2.7']

_LOGGER = logging.getLogger(__name__)

# Usually, only the controller does client api I/O during update() to pull
# current state - the exception is when zones pull their own schedules.
# However, any entity can call methods that will (eventually) change state.
PARALLEL_UPDATES = 0

# these are specific to this component
DOMAIN = 'evohome'
DATA_EVOHOME = 'data_' + DOMAIN
DISPATCHER_EVOHOME = 'dispatcher_' + DOMAIN

MIN_TEMP = 5
MAX_TEMP = 35
MIN_SCAN_INTERVAL = 180

CONF_LOCATION_IDX = 'location_idx'

# Validation of the user's configuration.
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL,
                     default=MIN_SCAN_INTERVAL): cv.positive_int,

        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
    }),
}, extra=vol.ALLOW_EXTRA)


# these are for the controller's opmode/state and the zone's state
EVO_RESET = 'AutoWithReset'
EVO_AUTO = 'Auto'
EVO_AUTOECO = 'AutoWithEco'
EVO_AWAY = 'Away'
EVO_DAYOFF = 'DayOff'
EVO_CUSTOM = 'Custom'
EVO_HEATOFF = 'HeatingOff'

TCS_MODES = [
    EVO_RESET,
    EVO_AUTO,
    EVO_AUTOECO,
    EVO_AWAY,
    EVO_DAYOFF,
    EVO_CUSTOM,
    EVO_HEATOFF
]

# bit masks for dispatcher packets
EVO_MASTER = 0x01
EVO_SLAVE = 0x02

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
    # scan_interval - rounded up to nearest 60 secs, with a minimum value
    domain_data['params'][CONF_SCAN_INTERVAL] \
        = (int((config[DOMAIN][CONF_SCAN_INTERVAL] - 1) / 60) + 1) * 60
    domain_data['params'][CONF_SCAN_INTERVAL] = \
        max(domain_data['params'][CONF_SCAN_INTERVAL], MIN_SCAN_INTERVAL)

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

    except requests.RequestException as err:
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
            "setup(): Config parameter, '%s'= %s , is out of range (0-%s), "
            "continuing with '%s' = 0.",
            CONF_LOCATION_IDX,
            loc_idx,
            len(client.installation_info) - 1,
            CONF_LOCATION_IDX
        )

        domain_data['params'][CONF_LOCATION_IDX] = 0
        domain_data['config'] = client.installation_info[0]

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
            'to': EVO_MASTER
        }
        hass.helpers.dispatcher.dispatcher_send(
            DISPATCHER_EVOHOME,
            pkt
        )

    hass.bus.listen(EVENT_HOMEASSISTANT_START, _first_update)

    load_platform(hass, 'climate', DOMAIN)

    return True


class EvoEntity(Entity):                                                        # noqa: D204,E501
    """Base for Honeywell evohome slave devices (Heating/DHW zones)."""
                                                                                # noqa: E116,E501; pylint: disable=no-member
    def __init__(self, hass, client, obj_ref):
        """Initialize the evohome entity.

        Most read-only properties are set here.  SOe are pseudo read-only,
        for example name (which can change).
        """
        # Set the usual object references
        self.hass = hass
        self.client = client
        domain_data = hass.data[DATA_EVOHOME]

        # Set the entity's own object reference & identifier
        self._id = obj_ref.systemId

        # Set the entity's configuration shortcut (considered static)
        self._config = domain_data['config'][GWS][0][TCS][0]
        self._params = domain_data['params']

        # Set the entity's name & icon (treated as static vales)
        self._name = domain_data['config']['locationInfo']['name']
        self._icon = "mdi:thermostat"

        # Set the entity's supported features
        self._supported_features = SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE

        # Set the entity's operation list - hard-coded for a particular order,
        # instead of using self._config['allowedSystemModes']
        self._op_list = TCS_MODES

        # Create timers, etc. - they're maintained in update(), or schedule()
        self._status = {}
        self._timers = domain_data['timers']

        self._timers['statusUpdated'] = datetime.min
        domain_data['schedules'] = {}

        # Set the entity's (initial) behaviour
        self._available = False  # will be True after first update()
        self._should_poll = True

        # Create a listener for (internal) update packets...
        hass.helpers.dispatcher.dispatcher_connect(
            DISPATCHER_EVOHOME,
            self._connect
        )  # for: def async_dispatcher_connect(signal, target)

    def _handle_requests_exceptions(self, err_hint, err):
        # evohomeclient v1 api (<=0.2.7) does not handle requests exceptions,
        # but we can catch them and extract the r.response, incl.:
        # {
        #   'code':    'TooManyRequests',
        #   'message': 'Request count limitation exceeded, ...'
        # }
        if err_hint == "TooManyRequests":  # not actually from requests library
            api_rate_limit_exceeded = True
            api_ver = "v1"

        # evohomeclient v2 api (>=0.2.7) exposes requests exceptions, incl.:
        # - HTTP_BAD_REQUEST, is usually Bad user credentials
        # - HTTP_TOO_MANY_REQUESTS, is api usuage limit exceeded
        # - HTTP_SERVICE_UNAVAILABLE, is often Vendor's fault
        elif err_hint == "HTTPError" and \
                str(HTTP_TOO_MANY_REQUESTS) in str(err):
            api_rate_limit_exceeded = True
            api_ver = "v2"

        # we can't handle any other exceptions here
        else:
            api_rate_limit_exceeded = False

        # do we need to back off?
        if api_rate_limit_exceeded is True:
            # so increase the scan_interval
            old_scan_interval = self._params[CONF_SCAN_INTERVAL]
            new_scan_interval = min(old_scan_interval * 2, 300)
            self._params[CONF_SCAN_INTERVAL] = new_scan_interval

            _LOGGER.warning(
                "API rate limit has been exceeded (for %s api), "
                "increasing '%s' from %s to %s seconds, and "
                "suspending polling for (at least) %s seconds.",
                api_ver,
                CONF_SCAN_INTERVAL,
                old_scan_interval,
                new_scan_interval,
                new_scan_interval * 3
            )

            # and also wait for a short while - 3 scan_intervals
            self._timers['statusUpdated'] = datetime.now() + \
                timedelta(seconds=new_scan_interval * 3)

        else:
            raise err

    @callback
    def _connect(self, packet):
        """Process a dispatcher connect."""
        if packet['to'] & self._type and packet['signal'] == 'update':
            self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name to use in the frontend UI."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend UI."""
        return self._icon

    @property
    def available(self):
        """Return True is the device is available.

        All evohome entities are initially unavailable. Once HA has started,
        state data is then retrieved by the Controller, and then the slaves
        will get a state (e.g. operating_mode, current_temperature).

        However, evohome entities can become unavailable for other reasons.
        """
        return self._available

    @property
    def supported_features(self):
        """Get the list of supported features of the Controller."""
        return self._supported_features

    @property
    def operation_list(self):
        """Return the list of available operations.

        Note that, for evohome, the operating mode is determined by - but not
        equivalent to - the last operation (from the operation list).
        """
        return self._op_list

    @property
    def current_operation(self):
        """Return the operation mode of the evohome entity."""
        return self._status['systemModeStatus']['mode']


class EvoController(EvoEntity, ClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the master of all
    the slave (CH/DHW) devices.
    """

    def __init__(self, hass, client, obj_ref):
        """Initialize the evohome Controller."""
        self._obj = obj_ref
        self._type = EVO_MASTER

        super().__init__(hass, client, obj_ref)

        if _LOGGER.isEnabledFor(logging.DEBUG):
            tmp_dict = dict(self._config)
            if 'zones' in tmp_dict:
                tmp_dict['zones'] = '...'
            if 'dhw' in tmp_dict:
                tmp_dict['dhw'] = '...'

            _LOGGER.debug(
                "__init__(%s), self._config = %s",
                self._id + " [" + self._name + "]",
                tmp_dict
            )
            _LOGGER.debug(
                "__init__(%s), self._timers = %s",
                self._id + " [" + self._name + "]",
                self._timers
            )
            _LOGGER.debug(
                "__init__(%s), self._params = %s",
                self._id + " [" + self._name + "]",
                self._params
            )

    @property
    def state(self):
        """Return the controller's current state.

        The Controller's state is usually its current operation_mode. NB: After
        calling AutoWithReset, the controller will enter Auto mode.
        """
        if self._status['systemModeStatus']['mode'] == EVO_RESET:
            state = EVO_AUTO
        else:
            state = self.current_operation
        return state

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._status['systemModeStatus']['mode'] == EVO_AWAY

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        'AutoWithReset may not be a mode in itself: instead, it _should_(?)
        lead to 'Auto' mode after resetting all the zones to 'FollowSchedule'.

        'HeatingOff' doesn't turn off heating, instead: it simply sets
        setpoints to a minimum value (i.e. FrostProtect mode).
        """
        if operation_mode in TCS_MODES:
            _LOGGER.debug(
                "set_operation_mode(): API call [1 request(s)]: "
                "tcs._set_status(%s)...",
                operation_mode
            )

            try:
                self._obj._set_status(operation_mode)                           # noqa: E501; pylint: disable=protected-access
            except requests.exceptions.HTTPError as err:
                self._handle_requests_exceptions("HTTPError", err)

        else:
            raise NotImplementedError()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self.set_operation_mode(EVO_AWAY)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self.set_operation_mode(EVO_AUTO)

    def _update_state_data(self, domain_data):
        client = domain_data['client']
        loc_idx = domain_data['params'][CONF_LOCATION_IDX]

        # Obtain latest state data (e.g. temperatures)...
        _LOGGER.debug(
            "_update_state_data(): API call [1 request(s)]: "
            "client.locations[loc_idx].status()..."
        )

        try:
            domain_data['status'].update(  # or: domain_data['status'] =
                client.locations[loc_idx].status()[GWS][0][TCS][0])

        except requests.exceptions.HTTPError as err:
            # check if we've exceeded the api rate limit
            self._handle_requests_exceptions("HTTPError", err)

        else:
            # only update the timers if the api call was successful
            domain_data['timers']['statusUpdated'] = datetime.now()

        _LOGGER.debug(
            "_update_state_data(): domain_data['status'] = %s",
            domain_data['status']
        )

    def update(self):
        """Get the latest state data of the installation.

        This includes state data for the Controller and its slave devices, such
        as the operating_mode of the Controller and the current_temperature
        of slaves.

        This is not asyncio-friendly due to the underlying client api.
        """
        domain_data = self.hass.data[DATA_EVOHOME]

        # Wait a minimum (scan_interval/60) mins (rounded up) between updates
        timeout = datetime.now() + timedelta(seconds=55)
        expired = timeout > self._timers['statusUpdated'] + \
            timedelta(seconds=domain_data['params'][CONF_SCAN_INTERVAL])

        if not expired:  # timer not expired, so exit
            return True

        # If we reached here, then it is time to update state data.  NB: unlike
        # all other config/state data, zones maintain their own schedules.
        self._update_state_data(domain_data)
        self._status = domain_data['status']

        if _LOGGER.isEnabledFor(logging.DEBUG):
            tmp_dict = dict(self._status)
            if 'zones' in tmp_dict:
                tmp_dict['zones'] = '...'
            if 'dhw' in tmp_dict:
                tmp_dict['dhw'] = '...'

            _LOGGER.debug(
                "update(%s), self._status = %s",
                self._id + " [" + self._name + "]",
                tmp_dict
            )
            _LOGGER.debug(
                "update(%s), self._timers = %s",
                self._id + " [" + self._name + "]",
                self._timers
            )

        no_recent_updates = self._timers['statusUpdated'] < datetime.now() - \
            timedelta(seconds=self._params[CONF_SCAN_INTERVAL] * 3.1)

        if no_recent_updates:
            # unavailable because no successful update()s (but why?)
            self._available = False
            debug_code = '0x01'

        elif not self._status:  # self._status == {}
            # unavailable because no status (but how? other than at startup?)
            self._available = False
            debug_code = '0x02'

        else:  # is available
            self._available = True

        if not self._available and \
                self._timers['statusUpdated'] != datetime.min:
            # this isn't the first (un)available (i.e. after STARTUP), so...
            _LOGGER.warning(
                "The entity, %s, is unavailable "
                "(i.e. self.available() = False), debug code is: %s",
                self._id + " [" + self._name + "]",
                debug_code
            )

        return True

    @property
    def target_temperature(self):
        """Return the average target temperature of the Heating/DHW zones."""
        temps = [zone['setpointStatus']['targetHeatTemperature']
                 for zone in self._status['zones']]

        avg_temp = sum(temps) / len(temps) if temps else None
        return round(avg_temp, 1)

    @property
    def current_temperature(self):
        """Return the average current temperature of the Heating/DHW zones."""
        tmp_list = [x for x in self._status['zones']
                    if x['temperatureStatus']['isAvailable'] is True]
        temps = [zone['temperatureStatus']['temperature'] for zone in tmp_list]

        avg_temp = sum(temps) / len(temps) if temps else None
        return round(avg_temp, 1)

    @property
    def temperature_unit(self):
        """Return the temperature unit to use in the frontend UI."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the temperature precision to use in the frontend UI."""
        return PRECISION_TENTHS

    @property
    def min_temp(self):
        """Return the minimum target temp (setpoint) of a evohome entity."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum target temp (setpoint) of a evohome entity."""
        return MAX_TEMP
