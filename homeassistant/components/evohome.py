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

# List of future features
# Replace AutoWithEco: mode that allows a delta of +/-0.5, +/-1.0, +/-1.5, etc.
# Improve heuristics: detect TRV Off, and OpenWindow (or remove altogether?)

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

    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,

    HTTP_BAD_REQUEST,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_SERVICE_UNAVAILABLE,
)

# These are HTTP codes commonly seen with this component
#   HTTP_BAD_REQUEST = 400          # usually, bad user credentials
#   HTTP_TOO_MANY_REQUESTS = 429    # usually, api limit exceeded
#   HTTP_SERVICE_UNAVAILABLE = 503  # this is common with Honeywell's websites

from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.entity import Entity

# these are specific to this component
ATTR_UNTIL = 'until'

# only the controller does client api I/O during update() to get current state
# however, any entity can call methdos that will change state
PARALLEL_UPDATES = 0

# these are specific to this component
CONF_LOCATION_IDX = 'location_idx'

REQUIREMENTS = ['evohomeclient==0.2.7']

# https://www.home-assistant.io/components/logger/
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'evohome'
DATA_EVOHOME = 'data_evohome'
DISPATCHER_EVOHOME = 'dispatcher_evohome'
MIN_TEMP = 5
MAX_TEMP = 35
MIN_SCAN_INTERVAL = 180

# Validation of the user's configuration.
CV_FLOAT = vol.All(vol.Coerce(float), vol.Range(min=MIN_TEMP, max=MAX_TEMP))

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
# these are for zones' opmode, and state
EVO_FOLLOW = 'FollowSchedule'
EVO_TEMPOVER = 'TemporaryOverride'
EVO_PERMOVER = 'PermanentOverride'
EVO_FROSTMODE = 'FrostProtect'

# bit masks for dispatcher packets
EVO_MASTER = 0x01
EVO_SLAVE = 0x02

# these are used to help prevent E501 (line too long) violations
GWS = 'gateways'
TCS = 'temperatureControlSystems'

# other stuff
TCS_MODES = [
    EVO_RESET,
    EVO_AUTO,
    EVO_AUTOECO,
    EVO_AWAY,
    EVO_DAYOFF,
    EVO_CUSTOM,
    EVO_HEATOFF
]
DHW_STATES = {STATE_ON: 'On', STATE_OFF: 'Off'}


def setup(hass, config):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    One controller with 0+ heating zones (e.g. TRVs, relays) and, optionally, a
    DHW controller.  Does not work for US-based systems.
    """
# 0. internal data, such as installation, state & timers...
    hass.data[DATA_EVOHOME] = {}

    domain_data = hass.data[DATA_EVOHOME]
    domain_data['timers'] = {}

# 1. pull the configuration parameters...
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

# 2. instantiate the client
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
        # ...then restore the it to what it was before instantiating the client
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
            # back off and try again later
            raise PlatformNotReady(err)

    finally:  # redact username, password as no longer needed
        del domain_data['params'][CONF_USERNAME]  # = 'REDACTED'
        del domain_data['params'][CONF_PASSWORD]  # = 'REDACTED'

    domain_data['client'] = client


# 3. REDACT any installation data we'll never need
    if client.installation_info[0]['locationInfo']['locationId'] != 'REDACTED':
        for loc in client.installation_info:
            loc['locationInfo']['locationId'] = 'REDACTED'
            loc['locationInfo']['streetAddress'] = 'REDACTED'
            loc['locationInfo']['city'] = 'REDACTED'
            loc['locationInfo']['locationOwner'] = 'REDACTED'
            loc[GWS][0]['gatewayInfo'] = 'REDACTED'

# 3a.
    loc_idx = domain_data['params'][CONF_LOCATION_IDX]

    try:
        domain_data['config'] = client.installation_info[loc_idx]

    # IndexError: configured location index is outside the range this login
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

# 3. Finished - do we need to output debgging info? If so...
    if _LOGGER.isEnabledFor(logging.DEBUG):
        _LOGGER.debug(
            "setup(): Location/TCS (temp. control system) used is: %s [%s]",
            domain_data['config'][GWS][0][TCS][0]['systemId'],
            domain_data['config']['locationInfo']['name']
        )
        # Some of this data needs further redaction before being logged
        tmp = dict(domain_data['config'])
        tmp['locationInfo']['postcode'] = 'REDACTED'

#       _LOGGER.debug("setup(): domain_data['config']: %s", tmp)


# Now we're ready to go, but we have no state as yet, so...
    def _first_update(event):
        """Let the controller know it can obtain it's first update."""
    # send a message to the master to do its first update
        pkt = {
            'sender': 'setup()',
            'signal': 'update',
            'to': EVO_MASTER
        }
        hass.helpers.dispatcher.async_dispatcher_send(
            DISPATCHER_EVOHOME,
            pkt
        )

# create a listener for the above...
    hass.bus.listen(EVENT_HOMEASSISTANT_START, _first_update)

# ... then finally, load the platform...
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
# set the usual object references
        self.hass = hass
        self.client = client
        domain_data = hass.data[DATA_EVOHOME]

# set the entity's own object reference & identifier
        self._id = obj_ref.systemId

# set the entity's configuration shortcut (considered static)
        self._config = domain_data['config'][GWS][0][TCS][0]
        self._params = domain_data['params']

# set the entity's name & icon (treated as static vales)
        self._name = domain_data['config']['locationInfo']['name']
        self._icon = "mdi:thermostat"

# set the entity's supported features
        self._supported_features = SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE

# set the entity's operation list (hard-coded so for a particular order)
        # lf._config['allowedSystemModes']
        self._op_list = [
            EVO_RESET,
            EVO_AUTO,
            EVO_AUTOECO,
            EVO_AWAY,
            EVO_DAYOFF,
            EVO_CUSTOM,
            EVO_HEATOFF
        ]

# create timers, etc. here, but they're maintained in update(), schedule()
        self._status = {}
        self._timers = domain_data['timers']

        self._timers['statusUpdated'] = datetime.min
        domain_data['schedules'] = {}

# set the entity's (initial) behaviour
        self._available = False  # will be True after first update()
        self._should_poll = True

# create a listener for (internal) update packets...
        hass.helpers.dispatcher.async_dispatcher_connect(
            DISPATCHER_EVOHOME,
            self._connect
        )  # for: def async_dispatcher_connect(signal, target)

    def _handle_requests_exceptions(self, err_type, err):

        domain_data = self.hass.data[DATA_EVOHOME]

# evohomeclient1 (<=0.2.7) does not have a requests exceptions handler:
#     File ".../evohomeclient/__init__.py", line 33, in _populate_full_data
#       userId = self.user_data['userInfo']['userID']
#   TypeError: list indices must be integers or slices, not str

# but we can (sometimes) extract the response, which may be like this:
# {
#   'code':    'TooManyRequests',
#   'message': 'Request count limitation exceeded, please try again later.'
# }

        if err_type == "TooManyRequests":  # not actually from requests library
            # v1 api limit has been exceeded
            old_scan_interval = domain_data['params'][CONF_SCAN_INTERVAL]
            new_scan_interval = min(old_scan_interval * 2, 300)
            domain_data['params'][CONF_SCAN_INTERVAL] = new_scan_interval

            _LOGGER.warning(
                "v1 API rate limit has been exceeded, suspending polling "
                "for %s seconds, & increasing '%s' from %s to %s seconds.",
                new_scan_interval * 3,
                CONF_SCAN_INTERVAL,
                old_scan_interval,
                new_scan_interval
            )

            domain_data['timers']['statusUpdated'] = datetime.now() + \
                timedelta(seconds=new_scan_interval * 3)

# evohomeclient2 (>=0.2.7) now exposes requests exceptions, e.g.:
# - "Connection reset by peer"
# - "Max retries exceeded with url", caused by "Connection timed out"
#       elif err_type == "ConnectionError":  # seems common with evohome
#           pass

# evohomeclient2 (>=0.2.7) now exposes requests exceptions, e.g.:
# - "400 Client Error: Bad Request for url" (e.g. Bad credentials)
# - "429 Client Error: Too Many Requests for url" (api usuage limit exceeded)
# - "503 Client Error: Service Unavailable for url" (e.g. website down)
        elif err_type == "HTTPError":
            if str(HTTP_TOO_MANY_REQUESTS) in str(err):
                # v2 api limit has been exceeded
                old_scan_interval = domain_data['params'][CONF_SCAN_INTERVAL]
                new_scan_interval = max(old_scan_interval * 2, 300)
                domain_data['params'][CONF_SCAN_INTERVAL] = new_scan_interval

                _LOGGER.warning(
                    "v2 API rate limit has been exceeded, suspending polling "
                    "for %s seconds, & increasing '%s' from %s to %s seconds.",
                    new_scan_interval * 3,
                    CONF_SCAN_INTERVAL,
                    old_scan_interval,
                    new_scan_interval
                )

                domain_data['timers']['statusUpdated'] = datetime.now() + \
                    timedelta(seconds=new_scan_interval * 3)

            elif str(HTTP_SERVICE_UNAVAILABLE) in str(err):
                # this appears to be common with Honeywell servers
                pass

    @callback
    def _connect(self, packet):
        """Process a dispatcher connect."""
#       _LOGGER.debug("_connect(%s): got packet %s", self._id, packet)

        if packet['to'] & self._type:
            if packet['signal'] == 'update':
                # for all entity types this must have force_refresh=True
                self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name to use in the frontend UI."""
#       _LOGGER.debug("name(%s) = %s", self._id, self._name)
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend UI."""
#       _LOGGER.debug("icon(%s) = %s", self._id, self._icon)
        return self._icon

    @property
    def available(self):
        """Return True is the device is available.

        All evohome entities are initially unavailable. Once HA has started,
        state data is then retrieved by the Controller, and then the slaves
        will get a state (e.g. operating_mode, current_temperature).

        However, evohome entities can become unavailable for other reasons.
        """
        no_recent_updates = self._timers['statusUpdated'] < datetime.now() - \
            timedelta(seconds=self._params[CONF_SCAN_INTERVAL] * 2.1)

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
            # this isn't the first (un)available (i.e. is after 1st update())
            _LOGGER.warning(
                "available(%s) = %s, debug code = %s, self._status = %s",
                self._id,
                self._available,
                debug_code,
                self._status
            )

#       _LOGGER.debug("available(%s) = %s", self._id, self._available)
        return self._available

    @property
    def supported_features(self):
        """Get the list of supported features of the Controller."""
        feats = self._supported_features
        _LOGGER.debug("supported_features(%s) = %s", self._id, feats)
        return self._supported_features

    @property
    def operation_list(self):
        """Return the list of available operations.

        Note that, for evohome, the operating mode is determined by - but not
        equivalent to - the last operation (from the operation list).
        """
#       _LOGGER.debug("operation_list(%s) = %s", self._id, self._op_list)
        return self._op_list

    @property
    def current_operation(self):
        """Return the operation mode of the evohome entity."""
        curr_op = self._status['systemModeStatus']['mode']
        _LOGGER.debug("current_operation(%s) = %s", self._id, curr_op)
        return curr_op


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
            _LOGGER.debug(
                "__init__(%s), self._params = %s",
                self._id + " [" + self._name + "]",
                self._params
            )
            _LOGGER.debug(
                "__init__(%s), self._timers = %s",
                self._id + " [" + self._name + "]",
                self._timers
            )
            config = dict(self._config)
            config['zones'] = '...'
            _LOGGER.debug(
                "__init__(%s), self.config = %s",
                self._id + " [" + self._name + "]",
                config
            )

    @property
    def state(self):
        """Return the controller's current state.

        The Controller's state is usually its current operation_mode. NB: After
        calling AutoWithReset, the controller will enter Auto mode.
        """
        if self._status['systemModeStatus']['mode'] == EVO_RESET:
            state = EVO_AUTO
        else:  # usually = self.current_operation
            state = self.current_operation

        _LOGGER.debug("state(%s) = %s", self._id, state)
        return state

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        away_mode = self._status['systemModeStatus']['mode'] == EVO_AWAY
        _LOGGER.debug("is_away_mode_on(%s) = %s", self._id, away_mode)
        return away_mode

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        'AutoWithReset may not be a mode in itself: instead, it _should_(?)
        lead to 'Auto' mode after resetting all the zones to 'FollowSchedule'.

        'HeatingOff' doesn't turn off heating, instead: it simply sets
        setpoints to a minimum value (i.e. FrostProtect mode).
        """
        _LOGGER.debug(
            "set_operation_mode(%s, operation_mode=%s), current mode = %s",
            self._id,
            operation_mode,
            self._status['systemModeStatus']['mode']
        )

# PART 1: Call the api
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
        _LOGGER.debug("turn_away_mode_on(%s)", self._id)
        self.set_operation_mode(EVO_AWAY)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        _LOGGER.debug("turn_away_mode_off(%s)", self._id)
        self.set_operation_mode(EVO_AUTO)

    def _update_state_data(self, domain_data):
        client = domain_data['client']
        loc_idx = domain_data['params'][CONF_LOCATION_IDX]

        # Obtain latest state data (e.g. temps)...
        _LOGGER.debug(
            "_update_state_data(): API call [1 request(s)]: "
            "client.locations[loc_idx].status()..."
        )

        try:
            domain_data['status'].update(  # or: domain_data['status'] =
                client.locations[loc_idx].status()[GWS][0][TCS][0])

        except requests.exceptions.HTTPError as err:
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

# it is time to update state data
# NB: unlike all other config/state data, zones maintain their own schedules
        self._update_state_data(domain_data)
        self._status = domain_data['status']

        _LOGGER.debug(
            "update(%s), self._status = %s",
            self._id,
            self._status
        )

        return True

    @property
    def target_temperature(self):
        """Return the average target temperature of the Heating/DHW zones."""
        num_temps = total_temp = 0
        for zone in self._status['zones']:
            num_temps = num_temps + 1
            total_temp = total_temp + \
                zone['setpointStatus']['targetHeatTemperature']

        avg_temp = total_temp / num_temps if num_temps > 0 else None

        _LOGGER.debug("current_temperature(%s) = %s", self._id, avg_temp)
        return avg_temp

    @property
    def current_temperature(self):
        """Return the average current temperature of the Heating/DHW zones."""
        num_temps = total_temp = 0
        for zone in self._status['zones']:
            if zone['temperatureStatus']['isAvailable'] is True:
                num_temps = num_temps + 1
                total_temp = total_temp + \
                    zone['temperatureStatus']['temperature']

        avg_temp = total_temp / num_temps if num_temps > 0 else None

        _LOGGER.debug("current_temperature(%s) = %s", self._id, avg_temp)
        return avg_temp

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
        """Return the minimum target temp (setpoint) of a zone."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum target temp (setpoint) of a zone."""
        return MAX_TEMP
