"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

A minimal configuration.yaml is as as below:

evohome:
  username: !secret evohome_username
  password: !secret evohome_password

These config parameters are presented with their default values:

# scan_interval: 300     # seconds, you can probably get away with 60
# high_precision: true   # tenths instead of halves
# location_idx: 0        # if you have more than 1 location, use this

These config parameters are YMMV:

# use_heuristics: false  # this is for the highly adventurous person, YMMV
# use_schedules: false   # this is for the slightly adventurous person
# away_temp: 15.0        # °C, if you have a non-default Away temp
# off_temp: 5.0          # °C, if you have a non-default Heating Off temp

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
# Improve hueristics: detect TRV Off, and OpenWindow

import logging
from datetime import datetime, timedelta
import requests
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateDevice,

    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE,
    SUPPORT_ON_OFF,

    ATTR_CURRENT_TEMPERATURE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_STEP,
    ATTR_OPERATION_MODE,
    ATTR_OPERATION_LIST,
    ATTR_AWAY_MODE,
)

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,

    EVENT_HOMEASSISTANT_START,
    PRECISION_WHOLE,
    PRECISION_HALVES,
    PRECISION_TENTHS,

    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
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
from homeassistant.helpers.temperature import display_temp as show_temp

# these are specific to this component
ATTR_UNTIL = 'until'

# only the controller does client api I/O during update() to get current state
# however, any entity can call methdos that will change state
PARALLEL_UPDATES = 0

# these are specific to this component
CONF_HIGH_PRECISION = 'high_precision'
CONF_USE_HEURISTICS = 'use_heuristics'
CONF_USE_SCHEDULES = 'use_schedules'
CONF_LOCATION_IDX = 'location_idx'
CONF_AWAY_TEMP = 'away_temp'
CONF_OFF_TEMP = 'off_temp'

API_VER = '0.2.7'  # alternatively, '0.2.5' is the version used elsewhere in HA

if API_VER == '0.2.7':  # these vars for >=0.2.6 (is it v3 of the api?)...
    REQUIREMENTS = ['evohomeclient==0.2.7']
    SETPOINT_CAPABILITIES = 'setpointCapabilities'
    SETPOINT_STATE = 'setpointStatus'
    TARGET_TEMPERATURE = 'targetHeatTemperature'
else:  # these vars for <=0.2.5...
    REQUIREMENTS = ['evohomeclient==0.2.5']
    SETPOINT_CAPABILITIES = 'heatSetpointCapabilities'
    SETPOINT_STATE = 'heatSetpointStatus'
    TARGET_TEMPERATURE = 'targetTemperature'

# https://www.home-assistant.io/components/logger/
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'evohome'
DATA_EVOHOME = 'data_evohome'
DISPATCHER_EVOHOME = 'dispatcher_evohome'

# Validation of the user's configuration.
CV_FLOAT = vol.All(vol.Coerce(float), vol.Range(min=5.0, max=35.0))

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=180): cv.positive_int,

        vol.Optional(CONF_HIGH_PRECISION, default=True): cv.boolean,
        vol.Optional(CONF_USE_HEURISTICS, default=False): cv.boolean,
        vol.Optional(CONF_USE_SCHEDULES, default=False): cv.boolean,

        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
        vol.Optional(CONF_AWAY_TEMP, default=15.0): CV_FLOAT,
        vol.Optional(CONF_OFF_TEMP, default=5.0): CV_FLOAT,
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
EVO_OPENWINDOW = 'OpenWindow'
EVO_FROSTMODE = 'FrostProtect'

# bit masks for dispatcher packets
EVO_MASTER = 0x01
EVO_SLAVE = 0x02
EVO_ZONE = 0x04
EVO_DHW = 0x08
EVO_UNKNOWN = 0x10  # there shouldn't ever be any of these

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
    # scan_interval - rounded up to nearest 60 secz
    domain_data['params'][CONF_SCAN_INTERVAL] \
        = (int((config[DOMAIN][CONF_SCAN_INTERVAL] - 1) / 60) + 1) * 60

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

    if domain_data['params'][CONF_USE_HEURISTICS]:
        _LOGGER.warning(
            "setup(): '%s' = True. This feature is best efforts, and may "
            "return incorrect state data, especially with '%s' < 180.",
            CONF_USE_HEURISTICS,
            CONF_SCAN_INTERVAL
        )

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
#   for component in ('camera', 'vacuum', 'switch'):
#       discovery.load_platform(hass, component, DOMAIN, {}, config)
    load_platform(hass, 'climate', DOMAIN)
#   load_platform(hass, 'boiler', DOMAIN)

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
        if self._type & EVO_MASTER:
            self._id = obj_ref.systemId
        else:  # self._type & EVO_SLAVE:
            self._id = obj_ref.zoneId  # OK for DHW too, as == obj_ref.dhwId


# set the entity's configuration shortcut (considered static)
        temperature_control_system = domain_data['config'][GWS][0][TCS][0]

        if self._type & EVO_MASTER:
            self._config = temperature_control_system
#           self._config = domain_data['config']

        elif self._type & EVO_ZONE:
            for _zone in temperature_control_system['zones']:
                if _zone['zoneId'] == self._id:
                    self._config = _zone
                    break

        elif self._type & EVO_DHW:
            self._config = temperature_control_system['dhw']

        self._params = domain_data['params']


# set the entity's name & icon (treated as static vales)
        if self._type & EVO_MASTER:
            self._name = "_" + domain_data['config']['locationInfo']['name']
            self._icon = "mdi:thermostat"

        elif self._type & EVO_ZONE:
            self._name = self._config['name']  # or: self._obj.name
            self._icon = "mdi:radiator"

        elif self._type & EVO_DHW:
            # prefix to force to tail of list in UI
            self._name = "~DHW"
            self._icon = "mdi:thermometer-lines"


# set the entity's supported features
        if self._type & EVO_MASTER:
            self._supported_features = \
                SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE

        elif self._type & EVO_ZONE:
            self._supported_features = \
                SUPPORT_OPERATION_MODE | SUPPORT_TARGET_TEMPERATURE

        elif self._type & EVO_DHW:
            self._supported_features = \
                SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF


# set the entity's operation list (hard-coded so for a particular order)
        if self._type & EVO_MASTER:
            # self._config['allowedSystemModes']
            self._op_list = [
                EVO_RESET,
                EVO_AUTO,
                EVO_AUTOECO,
                EVO_AWAY,
                EVO_DAYOFF,
                EVO_CUSTOM,
                EVO_HEATOFF
            ]

        elif self._type & EVO_SLAVE:
            # self._config['setpointCapabilities']['allowedSetpointModes']
            self._op_list = [EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER]


# create timers, etc. here, but they're maintained in update(), schedule()
        self._status = {}
        self._timers = domain_data['timers']

        if self._type & EVO_MASTER:
            self._timers['statusUpdated'] = datetime.min
            # master is created before any slave
            domain_data['schedules'] = {}

        elif self._type & EVO_SLAVE:
            # slaves update their schedules themselves
            domain_data['schedules'][self._id] = {}

            self._schedule = domain_data['schedules'][self._id]
            self._schedule['updated'] = datetime.min


# set the entity's (initial) behaviour
        self._available = False  # will be True after first update()
        self._should_poll = bool(self._type & EVO_MASTER)


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

        elif self._status and (self._type & EVO_SLAVE):
            # (un)available because (web site via) client api says so
            self._available = \
                bool(self._status['temperatureStatus']['isAvailable'])
            debug_code = '0x03'

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
    def should_poll(self):
        """Only the Controller will ever be polled.

        The Controller is usually (but not always) polled, and it will obtain
        the state data for its slaves (which themselves are never polled).
        """
        if self._type & EVO_MASTER:
            pass  # the Controller will decide this as it goes along
        else:
            self._should_poll = False

#       _LOGGER.debug("should_poll(%s) = %s", self._id, self._should_poll)
        return self._should_poll

    @property
    def supported_features(self):
        """Get the list of supported features of the Controller."""
# It will likely be the case we need to support Away/Eco/Off modes in the HA
# fashion, even though evohome's implementation of these modes are subtly
# different - this will allow tight integration with the HA landscape e.g.
# Alexa/Google integration
#       feats = self._supported_features
#       _LOGGER.debug("supported_features(%s) = %s", self._id, feats)
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
        if self._type & EVO_MASTER:
            curr_op = self._status['systemModeStatus']['mode']
        elif self._type & EVO_ZONE:
            curr_op = self._status[SETPOINT_STATE]['setpointMode']
        elif self._type & EVO_DHW:
            curr_op = self._status['stateStatus']['mode']

#       _LOGGER.debug("current_operation(%s) = %s", self._id, curr_op)
        return curr_op

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        # Re: state_attributes(), HA assumes Climate objects have:
        # - self.current_temperature:      True for Heating & DHW zones
        # - self.target_temperature:       True for Heating zones only
        # - self.min_temp & self.max_temp: True for Heating zones only

        if self._type & EVO_SLAVE:
            # Zones & DHW controllers report a current temperature
            # they have different precision, & a zone's precision may change
            data = {
                ATTR_CURRENT_TEMPERATURE: show_temp(
                    self.hass,
                    self.current_temperature,
                    self.temperature_unit,
                    self.precision
                ),
            }
        else:
            # Controllers do not have a temperature at all
            data = {}

        if self._type & EVO_DHW:
            # Zones & DHW controllers report a current temperature
            # they have different precision, & a zone's precision may change
            # lowest possible target_temp
            data[ATTR_MIN_TEMP] = show_temp(
                self.hass,
                self.min_temp,
                self.temperature_unit,
                self.precision
            )
            # highest possible target_temp
            data[ATTR_MAX_TEMP] = show_temp(
                self.hass,
                self.max_temp,
                self.temperature_unit,
                self.precision
            )

        # Heating zones also have a target temperature (and a setpoint)
        if self._supported_features & SUPPORT_TARGET_TEMPERATURE:
            data[ATTR_TEMPERATURE] = show_temp(
                self.hass,
                self.target_temperature,
                self.temperature_unit,
                PRECISION_HALVES
            )
            # lowest possible target_temp
            data[ATTR_MIN_TEMP] = show_temp(
                self.hass,
                self.min_temp,
                self.temperature_unit,
                PRECISION_HALVES
            )
            # highest possible target_temp
            data[ATTR_MAX_TEMP] = show_temp(
                self.hass,
                self.max_temp,
                self.temperature_unit,
                PRECISION_HALVES
            )
            data[ATTR_TARGET_TEMP_STEP] = self.target_temperature_step

        # DHW zones (a.k.a. boilers) have a setpoint not exposed via the api
        if self._supported_features & SUPPORT_ON_OFF:
            pass

        # All evohome entitys have an operation mode& and operation list
        if self._supported_features & SUPPORT_OPERATION_MODE:
            data[ATTR_OPERATION_MODE] = self.current_operation
            data[ATTR_OPERATION_LIST] = self._op_list

        # Controllers support away mode (slaves, strictly speaking, do not)
        if self._supported_features & SUPPORT_AWAY_MODE:
            is_away = self.is_away_mode_on
            data[ATTR_AWAY_MODE] = STATE_ON if is_away else STATE_OFF

        _LOGGER.debug("state_attributes(%s) = %s", self._id, data)
        return data


class EvoController(EvoEntity):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the master of all
    the slave (CH/DHW) devices.
    """

    def __init__(self, hass, client, obj_ref):
        """Initialize the evohome Controller."""
        self._obj = obj_ref
        self._type = EVO_MASTER

# Note, for access to slave object references, can use:
# - heating zones:  self._obj._zones
# - DHW controller: self._obj.hotwater

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

    def async_set_operation_mode(self, operation_mode):
        """Set new operation mode (explicitly defined as not a ClimateDevice).

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(self.set_operation_mode, operation_mode)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        'AutoWithReset may not be a mode in itself: instead, it _should_(?)
        lead to 'Auto' mode after resetting all the zones to 'FollowSchedule'.

        'HeatingOff' doesn't turn off heating, instead: it simply sets
        setpoints to a minimum value (i.e. FrostProtect mode).
        """
#       domain_data = self.hass.data[DATA_EVOHOME]

# At the start, the first thing to do is stop polled updates() until after
# set_operation_mode() has been called/effected
#       domain_data['lastUpdated'] = datetime.now()
        self._should_poll = False

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
# These 2 lines obligate only 1 location/controller, the 3rd/4th works for 1+
# self.client._get_single_heating_system()._set_status(mode)
# self.client.set_status_normal
# self.client.locations[0]._gateways[0]._control_systems[0]._set_status(mode)
# self._obj._set_status(mode)
            try:
                self._obj._set_status(operation_mode)                           # noqa: E501; pylint: disable=protected-access
            except requests.exceptions.HTTPError as err:
                self._handle_requests_exceptions("HTTPError", err)

            if self._params[CONF_USE_HEURISTICS]:
                _LOGGER.debug(
                    "set_operation_mode(%s): Using heuristics to change "
                    "operating mode from '%s' to '%s'",
                    self._id,
                    self._status['systemModeStatus']['mode'],
                    operation_mode
                    )
                self._status['systemModeStatus']['mode'] = operation_mode
                self.async_schedule_update_ha_state(force_refresh=False)
        else:
            raise NotImplementedError()


# PART 3: HEURISTICS - update the internal state of the Zones
# For (slave) Zones, when the (master) Controller enters:
# EVO_AUTOECO, it resets EVO_TEMPOVER (but not EVO_PERMOVER) to EVO_FOLLOW
# EVO_DAYOFF,  it resets EVO_TEMPOVER (but not EVO_PERMOVER) to EVO_FOLLOW


# NEW WAY - first, set the operating modes (& states)
        if self._params[CONF_USE_HEURISTICS]:
            _LOGGER.debug(
                "set_operation_mode(): Using heuristics to change "
                "slave's operating modes",
                )

            for zone in self._status['zones']:
                if operation_mode == EVO_CUSTOM:
                    pass  # operating modes unknowable, must await update()
                elif operation_mode == EVO_RESET:
                    zone[SETPOINT_STATE]['setpointMode'] = EVO_FOLLOW
                else:
                    if zone[SETPOINT_STATE]['setpointMode'] != EVO_PERMOVER:
                        zone[SETPOINT_STATE]['setpointMode'] = EVO_FOLLOW

            # this section needs more testing
            if 'dhw' in self._status:
                zone = self._status['dhw']
                if operation_mode == EVO_CUSTOM:
                    pass  # op modes unknowable, must await next update()
                elif operation_mode == EVO_RESET:
                    zone['stateStatus']['mode'] = EVO_FOLLOW
                elif operation_mode == EVO_AWAY:
                    # DHW is turned off in Away mode
                    if zone['stateStatus']['mode'] != EVO_PERMOVER:
                        zone['stateStatus']['mode'] = EVO_FOLLOW
#                       zone['stateStatus']['status'] = STATE_OFF
                else:
                    pass


# Finally, inform the Zones that their state may have changed
            pkt = {
                'sender': 'controller',
                'signal': 'update',
                'to': EVO_SLAVE
            }
            self.hass.helpers.dispatcher.async_dispatcher_send(
                DISPATCHER_EVOHOME,
                pkt
            )

# At the end, the last thing to do is resume updates()
        self._should_poll = True

    def async_turn_away_mode_on(self):
        """Turn away mode on (explicitly defined as not a ClimateDevice).

        This method must be run in the event loop and returns a coroutine.
        """
#       _LOGGER.debug("async_turn_away_mode_on(%s)", self._id)
        return self.hass.async_add_job(self.turn_away_mode_on)

    def turn_away_mode_on(self):
        """Turn away mode on."""
        _LOGGER.debug("turn_away_mode_on(%s)", self._id)
        self.set_operation_mode(EVO_AWAY)

    def async_turn_away_mode_off(self):
        """Turn away mode off  (explicitly defined as not a ClimateDevice).

        This method must be run in the event loop and returns a coroutine.
        """
#       _LOGGER.debug("async_turn_away_mode_off(%s)", self._id)
        return self.hass.async_add_job(self.turn_away_mode_off)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        _LOGGER.debug("turn_away_mode_off(%s)", self._id)
        self.set_operation_mode(EVO_AUTO)

    def _update_state_data(self, domain_data):
        client = domain_data['client']
        loc_idx = domain_data['params'][CONF_LOCATION_IDX]

    # 1. Obtain latest state data (e.g. temps)...
        _LOGGER.debug(
            "_update_state_data(): API call [1 request(s)]: "
            "client.locations[loc_idx].status()..."
        )

        try:
            domain_data['status'].update(  # or: domain_data['status'] =
                client.locations[loc_idx].status()[GWS][0][TCS][0])

#       except requests.RequestException as err:
#
#       except requests.exceptions.ConnectionError as err:
#           self._handle_requests_exceptions("ConnectionError", err)
        except requests.exceptions.HTTPError as err:
            self._handle_requests_exceptions("HTTPError", err)

        else:
            # only update the timers if the api call was successful
            domain_data['timers']['statusUpdated'] = datetime.now()

        _LOGGER.debug("domain_data['status'] = %s", domain_data['status'])

    # 2. AFTER obtaining state data, do we need to increase precision of temps?
        if domain_data['params'][CONF_HIGH_PRECISION] and \
                len(client.locations) > 1:
            _LOGGER.warning(
                "Unable to increase temperature precision via the v1 api; "
                "there is more than one Location/TCS. Disabling this feature."
            )
            domain_data['params'][CONF_HIGH_PRECISION] = False

        elif domain_data['params'][CONF_HIGH_PRECISION]:
            _LOGGER.debug(
                "Trying to increase temperature precision via the v1 api..."
            )
            try:
                from evohomeclient import EvohomeClient as EvohomeClientVer1
                ec1_api = EvohomeClientVer1(client.username, client.password)

                _LOGGER.debug(
                    "_update_state_data(): Calling (v1) API [2 request(s)]: "
                    "client.temperatures()..."
                )
                # this is a a generator, so use list()
                # i think: DHW first (if any), then zones ordered by name
                new_dict_list = list(ec1_api.temperatures(force_refresh=True))

                _LOGGER.debug(
                    "_update_state_data(): new_dict_list = %s",
                    new_dict_list
                )

    # start prep of the data
                for zone in new_dict_list:
                    del zone['name']
                    zone['apiV1Status'] = {}
                    # is 128 is used for 'unavailable' temps?
                    temp = zone.pop('temp')
                    if temp != 128:
                        zone['apiV1Status']['temp'] = temp
                    else:
                        zone['apiV1Status']['temp'] = None

    # first handle the DHW, if any (done this way for readability)
                if new_dict_list[0]['thermostat'] == 'DOMESTIC_HOT_WATER':
                    dhw_v1 = new_dict_list.pop(0)

                    dhw_v1['dhwId'] = str(dhw_v1.pop('id'))
                    del dhw_v1['setpoint']
                    del dhw_v1['thermostat']

                    dhw_v2 = domain_data['status']['dhw']
                    dhw_v2.update(dhw_v1)  # more like a merge

    # now, prepare the v1 zones to merge into the v2 zones
                for zone in new_dict_list:
                    zone['zoneId'] = str(zone.pop('id'))
                    zone['apiV1Status']['setpoint'] = zone.pop('setpoint')
                    del zone['thermostat']

                org_dict_list = domain_data['status']['zones']

                _LOGGER.debug(
                    "_update_state_data(): org_dict_list = %s",
                    org_dict_list
                )

    # finally, merge the v1 zones into the v2 zones
    #  - dont use sorted(), it will create a new list!
                new_dict_list.sort(key=lambda x: x['zoneId'])
                org_dict_list.sort(key=lambda x: x['zoneId'])
                # v2 and v1 lists _should_ now be zip'ble
                for i, j in zip(org_dict_list, new_dict_list):
                    i.update(j)

            except TypeError:
                _LOGGER.warning(
                    "Failed to obtain higher-precision temperatures "
                    "via the v1 api.  Continuing with v2 temps for now."
                )

                if isinstance(ec1_api.user_data, list):
                    if 'code' in ec1_api.user_data[0]:
                        if ec1_api.user_data[0]['code'] == 'TooManyRequests':
                            self._handle_requests_exceptions(
                                ec1_api.user_data[0]['code'],
                                ec1_api.user_data[0]['message']
                            )

                elif _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "This may help: ec1_api.user_data = %s",
                        ec1_api.user_data
                    )
    #               raise  # usually, no raise for TypeError

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
#       self._should_poll = True

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

        if _LOGGER.isEnabledFor(logging.DEBUG):
            status = dict(self._status)  # create a copy since we're editing
#           if 'zones' in status:
#               status['zones'] = '...'
#           if 'dhw' in status:
#               status['dhw'] = '...'
            _LOGGER.debug(
                "update(%s), self._status = %s",
                self._id,
                status
            )

# Finally, send a message to the slaves to update themselves
        pkt = {
            'sender': 'controller',
            'signal': 'update',
            'to': EVO_SLAVE
        }
        self.hass.helpers.dispatcher.async_dispatcher_send(
            DISPATCHER_EVOHOME,
            pkt
        )

        return True


class EvoSlaveEntity(EvoEntity):
    """Base for Honeywell evohome slave devices (Heating/DHW zones)."""

    def __init__(self, hass, client, obj_ref):
        """Initialize the evohome evohome Heating/DHW zone."""
        self._obj = obj_ref

        if self._obj.zone_type == 'temperatureZone':
            self._type = EVO_SLAVE | EVO_ZONE
        elif self._obj.zone_type == 'domesticHotWater':
            self._type = EVO_SLAVE | EVO_DHW
        else:  # this should never happen!
            self._type = EVO_UNKNOWN

        super().__init__(hass, client, obj_ref)

        _LOGGER.debug(
            "__init__(%s), self._config = %s",
            self._id + " [" + self._name + "]",
            self._config
        )

    def _switchpoint(self, day_time=None, next_switchpoint=False):
        # return the switchpoint for a schedule at a particular day/time, for:
        # - heating zones: a time-from, and a target temp
        # - boilers: a time-from, and on (trying to reach target temp)/off
        schedule = self.schedule

        if day_time is None:
            day_time = datetime.now()
        day_of_week = int(day_time.strftime('%w'))  # 0 is Sunday
        time_of_day = day_time.strftime('%H:%M:%S')

        # start with the last switchpoint of the day before...
        idx = -1  # last switchpoint of the day before

        # iterate the day's switchpoints until we go past time_of_day...
        day = schedule['DailySchedules'][day_of_week]
        for i, tmp in enumerate(day['Switchpoints']):
            if time_of_day > tmp['TimeOfDay']:
                idx = i
            else:
                break

        # if asked, go for the next switchpoint...
        if next_switchpoint is True:  # the upcoming switchpoint
            if idx < len(day['Switchpoints']) - 1:
                day = schedule['DailySchedules'][day_of_week]
                switchpoint = day['Switchpoints'][idx + 1]
                switchpoint_date = day_time
            else:
                day = schedule['DailySchedules'][(day_of_week + 1) % 7]
                switchpoint = day['Switchpoints'][0]
                switchpoint_date = day_time + timedelta(days=1)

        else:  # the effective switchpoint
            if idx == -1:
                day = schedule['DailySchedules'][(day_of_week + 6) % 7]
                switchpoint = day['Switchpoints'][idx]
                switchpoint_date = day_time + timedelta(days=-1)
            else:
                day = schedule['DailySchedules'][day_of_week]
                switchpoint = day['Switchpoints'][idx]
                switchpoint_date = day_time

        # insert day_and_time of teh switchpoint for those who want it
        switchpoint['DateAndTime'] = switchpoint_date.strftime('%Y/%m/%d') + \
            " " + switchpoint['TimeOfDay']

#       _LOGGER.debug("_switchpoint(%s) = %s", self._id, switchpoint)
        return switchpoint

    def _next_switchpoint_time(self):
        # until either the next scheduled setpoint, or just an hour from now
        if self._params[CONF_USE_SCHEDULES]:
            # get the time of the next scheduled setpoint (switchpoint)
            switchpoint = self._switchpoint(next_switchpoint=True)
            # convert back to a datetime object
            until = datetime.strptime(switchpoint['DateAndTime'])
        else:
            # there are no schedfules, so use an hour from now
            until = datetime.now() + timedelta(hours=1)

        return until

    @property
    def schedule(self):
        """Return the schedule of a zone or a DHW controller."""
        if not self._params[CONF_USE_SCHEDULES]:
            _LOGGER.warning(
                "schedule(%s): '%s' = False, so schedules are not retrieved "
                "during update(). If schedules are required, set this "
                "configuration parameter to True and restart HA.",
                self._id,
                CONF_USE_SCHEDULES
            )
            return None

        return self._schedule['schedule']

    @property
    def device_state_attributes(self):
        """Return the optional device state attributes."""
        data = {}
        data['status'] = self._status
        data['switchpoints'] = {}

        if self._params[CONF_USE_SCHEDULES]:
            data['switchpoints']['current'] = self._switchpoint()
            data['switchpoints']['next'] = \
                self._switchpoint(next_switchpoint=True)

        _LOGGER.debug("device_state_attributes(%s) = %s", self._id, data)
        return data

    def async_set_operation_mode(self, operation_mode):
        """Set a new target operation mode.

        This method must be run in the event loop and returns a coroutine.  The
        underlying method is not asyncio-friendly.
        """
        return self.hass.async_add_job(self.set_operation_mode, operation_mode)  # noqa: E501; pylint: disable=no-member

    @property
    def current_temperature(self):
        """Return the current temperature of the Heating/DHW zone."""
        # this is used by evoZone, and evoBoiler class, however...
        # evoZone(Entity, ClimateDevice) uses temperature_unit, and
        # evoBoiler(Entity) *also* needs uses unit_of_measurement

        # TBA: this needs work - what if v1 temps failed, or ==128
        if 'apiV1Status' in self._status:
            curr_temp = self._status['apiV1Status']['temp']
        elif self._status['temperatureStatus']['isAvailable']:
            curr_temp = self._status['temperatureStatus']['temperature']
        else:
            # this isn't expected as available() should have been False
            curr_temp = None

        if curr_temp is None:
            _LOGGER.debug(
                "current_temperature(%s) - is unavailable",
                self._id
            )

        _LOGGER.debug("current_temperature(%s) = %s", self._id, curr_temp)
        return curr_temp

    @property
    def temperature_unit(self):
        """Return the temperature unit to use in the frontend UI."""
#       _LOGGER.debug("temperature_unit(%s) = %s", self._id, TEMP_CELSIUS)
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the temperature precision to use in the frontend UI."""
        if self._params[CONF_HIGH_PRECISION]:
            precision = PRECISION_TENTHS  # and is actually 0.01 for zones!
        elif self._type & EVO_ZONE:
            precision = PRECISION_HALVES
        elif self._type & EVO_DHW:
            precision = PRECISION_WHOLE

#       _LOGGER.debug("precision(%s) = %s", self._id, precision)
        return precision

    @property
    def min_temp(self):
        """Return the minimum target temp (setpoint) of a zone.

        Setpoints are 5-35C by default, but can be further limited.  Only
        applies to heating zones, not DHW controllers (boilers).
        """
        if self._type & EVO_ZONE:
            temp = self._config[SETPOINT_CAPABILITIES]['minHeatSetpoint']
        elif self._type & EVO_DHW:
            temp = 30
#       _LOGGER.debug("min_temp(%s) = %s", self._id, temp)
        return temp

    @property
    def max_temp(self):
        """Return the maximum target temp (setpoint) of a zone.

        Setpoints are 5-35C by default, but can be further limited.  Only
        applies to heating zones, not DHW controllers (boilers).
        """
        if self._type & EVO_ZONE:
            temp = self._config[SETPOINT_CAPABILITIES]['maxHeatSetpoint']
        elif self._type & EVO_DHW:
            temp = 85
#       _LOGGER.debug("max_temp(%s) = %s", self._id, temp)
        return temp

    def update(self):
        """Get the latest state data of the Heating/DHW zone.

        This includes state data obtained by the controller (e.g. temperature),
        but also state data obtained directly by the zone (i.e. schedule).

        This is not asyncio-friendly due to the underlying client api.
        """
# After (say) a controller.set_operation_mode, it will take a while for the
# 1. (invoked) client api call (request.xxx) to reach the web server,
# 2. web server to send message to the controller
# 3. controller to get message to zones (they'll answer immediately)
# 4. controller to send response back to web server
# 5. we make next client api call (every scan_interval)
# ... in between 1. & 5., should assumed_state/available/other be True/False?
        domain_data = self.hass.data[DATA_EVOHOME]

# Part 1: state - create pointers to state as retrieved by the controller
        if self._type & EVO_ZONE:
            for _zone in domain_data['status']['zones']:
                if _zone['zoneId'] == self._id:
                    self._status = _zone
                    break

        elif self._type & EVO_DHW:
            self._status = domain_data['status']['dhw']

        _LOGGER.debug(
            "update(%s), self._status = %s",
            self._id,
            self._status
        )

# Part 2: schedule - retrieved here as required
        if self._params[CONF_USE_SCHEDULES]:
            self._schedule = domain_data['schedules'][self._id]

            # Use cached schedule if < 60 mins old
            timeout = datetime.now() + timedelta(seconds=59)
            expired = timeout > self._schedule['updated'] + timedelta(hours=1)

            if expired:  # timer expired, so update schedule
                if self._type & EVO_ZONE:
                    _LOGGER.debug(
                        "update(): API call [1 request(s)]: "
                        "zone(%s).schedule()...",
                        self._id
                    )
                else:  # elif self._type & EVO_DHW:
                    _LOGGER.debug(
                        "update(): API call [1 request(s)]: "
                        "dhw(%s).schedule()...",
                        self._id
                    )
                self._schedule['schedule'] = {}
                self._schedule['updated'] = datetime.min

                try:
                    self._schedule['schedule'] = self._obj.schedule()
                except requests.exceptions.HTTPError as err:
                    self._handle_requests_exceptions("HTTPError", err)
                else:
                    # only update the timers if the api call was successful
                    self._schedule['updated'] = datetime.now()

                _LOGGER.debug(
                    "update(%s), self._schedule = %s",
                    self._id,
                    self._schedule
                )

        return True


class EvoZone(EvoSlaveEntity, ClimateDevice):
    """Base for a Honeywell evohome heating zone (e.g. a TRV)."""

    @property
    def state(self):
        """Return the current state of a zone - usually, its operation mode.

        A zone's state is usually its operation mode, but they can enter
        OpenWindowMode autonomously, or they can be 'Off', or just set to 5.0C.
        In all three case, the client api seems to report 5C.

        This is complicated futher by the possibility that the minSetPoint is
        greater than 5C.
        """
# When Zone is 'Off' & TCS == Away: Zone = TempOver/5C
# When Zone is 'Follow' & TCS = Away: Zone = Follow/15C
        zone_op_mode = self._status[SETPOINT_STATE]['setpointMode']

        state = zone_op_mode

        # Optionally, use heuristics to override reported state (mode)
        if self._params[CONF_USE_HEURISTICS]:
            domain_data = self.hass.data[DATA_EVOHOME]

            tcs_op_mode = domain_data['status']['systemModeStatus']['mode']
            zone_target_temp = self._status[SETPOINT_STATE][TARGET_TEMPERATURE]

            if tcs_op_mode == EVO_RESET:
                state = EVO_AUTO
            elif tcs_op_mode == EVO_HEATOFF:
                state = EVO_FROSTMODE
            elif zone_op_mode == EVO_FOLLOW:
                state = tcs_op_mode

            if zone_target_temp == self.min_temp:
                if zone_op_mode == EVO_TEMPOVER:
                    # TRV turned to Off, or ?OpenWindowMode?
                    state = EVO_FROSTMODE + " (Off?)"
                elif zone_op_mode == EVO_PERMOVER:
                    state = EVO_FROSTMODE

            if state != self._status[SETPOINT_STATE]['setpointMode']:
                _LOGGER.warning(
                    "state(%s) = %s, via heuristics (via api = %s)",
                    self._id,
                    state,
                    self._status[SETPOINT_STATE]['setpointMode']
                )
            else:
                _LOGGER.debug(
                    "state(%s) = %s, via heuristics (via api = %s)",
                    self._id,
                    state,
                    self._status[SETPOINT_STATE]['setpointMode']
                )
        else:
            _LOGGER.debug("state(%s) = %s", self._id, state)
        return state

    def _set_temperature(self, temperature, until=None):
        """Set the new target temperature of a heating zone.

        Turn the temperature for:
          - an hour/until next setpoint (TemporaryOverride), or
          - indefinitely (PermanentOverride)

        The setpoint feature requires 'use_schedules' = True.

        Keyword arguments can be:
          - temperature (required)
          - until.strftime('%Y-%m-%dT%H:%M:%SZ') is:
            - +1h for TemporaryOverride if not using schedules, or
            - next setpoint for TemporaryOverride if using schedules
            - none for PermanentOverride
        """
# If is None: PermanentOverride - override target temp indefinitely
#  otherwise: TemporaryOverride - override target temp, until some time

        max_temp = self._config[SETPOINT_CAPABILITIES]['maxHeatSetpoint']
        if temperature > max_temp:
            _LOGGER.error(
                "set_temperature(%s): Temp %s is above maximum, %s! "
                "(cancelling call).",
                self._id + " [" + self._name + "]",
                temperature,
                max_temp
            )
            return False

        min_temp = self._config[SETPOINT_CAPABILITIES]['minHeatSetpoint']
        if temperature < min_temp:
            _LOGGER.error(
                "set_temperature(%s): Temp %s is below minimum, %s! "
                "(cancelling call).",
                self._id + " [" + self._name + "]",
                temperature,
                min_temp
            )
            return False

        _LOGGER.debug(
            "_set_temperature(): API call [1 request(s)]: "
            "zone(%s).set_temperature(%s, %s)...",
            self._id,
            temperature,
            until
        )
        try:
            self._obj.set_temperature(temperature)

        except requests.exceptions.HTTPError as err:
            self._handle_requests_exceptions("HTTPError", err)

        return None

    def set_temperature(self, **kwargs):
        """Set a target temperature (setpoint) for a zone.

        Only applies to heating zones, not DHW controllers (boilers).
        """
        _LOGGER.debug(
            "set_temperature(%s, **kwargs)",
            self._id + " [" + self._name + "]"
        )

#       for name, value in kwargs.items():
#           _LOGGER.debug('%s = %s', name, value)

        temperature = kwargs.get(ATTR_TEMPERATURE)

        if temperature is None:
            _LOGGER.error(
                "set_temperature(%s): Temperature must not be None "
                "(cancelling call).",
                self._id + " [" + self._name + "]"
            )
            return False

# if you change the temp on a evohome TRV, it is until next switchpoint
        until = kwargs.get(ATTR_UNTIL)
        if until is None:
            # until either the next scheduled setpoint, or just 1 hour from now
            if self._params[CONF_USE_SCHEDULES]:
                until = self._next_switchpoint_time
            else:
                until = datetime.now() + timedelta(hours=1)

        self._set_temperature(temperature, until)

# Optionally, use heuristics to update state
        if self._params[CONF_USE_HEURISTICS]:
            _LOGGER.debug(
                "set_operation_mode(): Action completed, "
                "updating local state data using heuristics..."
            )

            self._status[SETPOINT_STATE]['setpointMode'] \
                = EVO_PERMOVER if until is None else EVO_TEMPOVER

            self._status[SETPOINT_STATE][TARGET_TEMPERATURE] \
                = temperature

            _LOGGER.debug(
                "set_temperature(%s): Calling tcs.schedule_update_ha_state()",
                self._id
            )
            self.async_schedule_update_ha_state(force_refresh=False)

        return True

    def set_operation_mode(self, operation_mode, **kwargs):                     # noqa: E501; pylint: disable=arguments-differ
        # t_operation_mode(hass, operation_mode, entity_id=None):
        """Set an operating mode for a Zone.

        NB: evohome Zones do not have an operating mode as understood by HA.
        Instead they usually 'inherit' an operating mode from their controller.

        More correctly, these Zones are in a follow mode, where their setpoint
        temperatures are a function of their schedule, and the Controller's
        operating_mode, e.g. Economy mode is setpoint less (say) 3 degrees.

        Thus, you cannot set a Zone to Away mode, but the location (i.e. the
        Controller) is set to Away and each Zones's setpoints are adjusted
        accordingly (in this case, to 10 degrees by default).

        However, Zones can override these setpoints, either for a specified
        period of time, 'TemporaryOverride', after which they will revert back
        to 'FollowSchedule' mode, or indefinitely, 'PermanentOverride'.

        These three modes are treated as the Zone's operating mode and, as a
        consequence of the above, this method has 2 arguments in addition to
        operation_mode: temperature, and until.
        """
        temperature = kwargs.get(ATTR_TEMPERATURE)
        until = kwargs.get(ATTR_UNTIL)

        _LOGGER.debug(
            "set_operation_mode(%s, OpMode=%s, Temp=%s, Until=%s)",
            self._id,
            operation_mode,
            temperature,
            until
        )

# FollowSchedule - return to scheduled target temp (indefinitely)
        if operation_mode == EVO_FOLLOW:
            if temperature is not None or until is not None:
                _LOGGER.warning(
                    "set_operation_mode(%s): For '%s' mode, 'temperature "
                    "' and 'until' should both be None (will ignore them).",
                    self._id + " [" + self._name + "]",
                    operation_mode
                )

            _LOGGER.debug(
                "set_operation_mode(%s): API call [1 request(s)]: "
                "zone.cancel_temp_override()...",
                self._id
            )
            try:
                self._obj.cancel_temp_override(self._obj)

            except requests.exceptions.HTTPError as err:
                self._handle_requests_exceptions("HTTPError", err)

        else:
            if temperature is None:
                _LOGGER.warning(
                    "set_operation_mode(%s): For '%s' mode, 'temperature' "
                    "should not be None (will use current target temp).",
                    self._id,
                    operation_mode
                )
                temperature = self._status[SETPOINT_STATE][TARGET_TEMPERATURE]

# PermanentOverride - override target temp indefinitely
        if operation_mode == EVO_PERMOVER:
            if until is not None:
                _LOGGER.warning(
                    "set_operation_mode(%s): For '%s' mode, "
                    "'until' should be None (will ignore it).",
                    self._id,
                    operation_mode
                )

            self._set_temperature(temperature, until)

# TemporaryOverride - override target temp, for a hour by default
        elif operation_mode == EVO_TEMPOVER:
            if until is None:
                _LOGGER.warning(
                    "set_operation_mode(%s): For '%s' mode, 'until' should "
                    "not be None (will use until next switchpoint).",
                    self._id,
                    operation_mode
                )
# until either the next scheduled setpoint, or just an hour from now
                if self._params[CONF_USE_SCHEDULES]:
                    until = self._next_switchpoint_time
                else:
                    until = datetime.now() + timedelta(hours=1)

            self._set_temperature(temperature, until)

# Optionally, use heuristics to update state
        if self._params[CONF_USE_HEURISTICS]:
            _LOGGER.debug(
                "set_operation_mode(): Action completed, "
                "updating local state data using heuristics..."
            )

            self._status[SETPOINT_STATE]['setpointMode'] \
                = operation_mode

            if operation_mode == EVO_FOLLOW:
                if self._params[CONF_USE_SCHEDULES]:
                    self._status[SETPOINT_STATE][TARGET_TEMPERATURE] \
                        = self.setpoint
            else:
                self._status[SETPOINT_STATE][TARGET_TEMPERATURE] = temperature

            _LOGGER.debug(
                "Calling tcs.schedule_update_ha_state()"
            )
            self.async_schedule_update_ha_state(force_refresh=False)

        return True

    @property
    def setpoint(self):
        """Return the current (scheduled) setpoint temperature of a zone.

        This is the _scheduled_ target temperature, and not the actual target
        temperature, which would be a function of operating mode (both
        controller and zone) and, for TRVs, the OpenWindowMode feature.

        Boilers do not have setpoints; they are only on or off.  Their 
        (scheduled) setpoint is the same as their target temperature.
        """
        # Zones have: {'DhwState': 'On',     'TimeOfDay': '17:30:00'}
        # DHW has:    {'heatSetpoint': 17.3, 'TimeOfDay': '17:30:00'}
        setpoint = self._switchpoint()['heatSetpoint']
        _LOGGER.debug("setpoint(%s) = %s", self._id, setpoint)
        return setpoint

    @property
    def target_temperature(self):
        """Return the current target temperature of a zone.

        This is the _actual_ target temperature (a function of operating mode
        (controller and zone), and a TRVs own OpenWindowMode feature), and not
        the scheduled target temperature.
        """
# If a TRV is set to 'Off' via it's own controls, it shows up in the client api
# as 'TemporaryOverride' (not 'PermanentOverride'!), setpoint = min, until next
# switchpoint.  If you change the controller mode, then
        domain_data = self.hass.data[DATA_EVOHOME]

        temp = self._status[SETPOINT_STATE][TARGET_TEMPERATURE]

        if self._params[CONF_USE_HEURISTICS] and \
                self._params[CONF_USE_SCHEDULES]:

            tcs_opmode = domain_data['status']['systemModeStatus']['mode']
            zone_opmode = self._status[SETPOINT_STATE]['setpointMode']

            if tcs_opmode == EVO_CUSTOM:
                pass  # target temps unknowable, must await update()

            elif tcs_opmode in (EVO_AUTO, EVO_RESET) and \
                    zone_opmode == EVO_FOLLOW:
                # target temp is set according to schedule
                temp = self.setpoint

            elif tcs_opmode == EVO_AUTOECO and \
                    zone_opmode == EVO_FOLLOW:
                # target temp is relative to the scheduled setpoints, with
                #  - setpoint => 16.5, target temp = (setpoint - 3)
                #  - setpoint <= 16.0, target temp = (setpoint - 0)!
                temp = self.setpoint
                if temp > 16.0:
                    temp = temp - 3

            elif tcs_opmode == EVO_DAYOFF and \
                    zone_opmode == EVO_FOLLOW:
                # set target temp according to schedule, but for Saturday
                this_time_saturday = datetime.now() + timedelta(
                    days=6 - int(datetime.now().strftime('%w')))
                temp = self._switchpoint(day_time=this_time_saturday)
                temp = temp['heatSetpoint']

            elif tcs_opmode == EVO_AWAY:
                # default 'Away' temp is 15C, but can be set otherwise
                # TBC: set to CONF_AWAY_TEMP even if set setpoint is lower
                temp = self._params[CONF_AWAY_TEMP]

            elif tcs_opmode == EVO_HEATOFF:
                # default 'HeatingOff' temp is 5C, but can be set higher
                # the target temp can't be less than a zone's minimum setpoint
                temp = max(self._params[CONF_OFF_TEMP], self.min_temp)

            if temp != self._status[SETPOINT_STATE][TARGET_TEMPERATURE] and \
                    self.current_operation == EVO_FOLLOW:
                _LOGGER.warning(
                    "target_temperature(%s) = %s via heuristics "
                    "(via api = %s) - "
                    "if you can determine the cause of this discrepancy, "
                    "please consider submitting an issue via github",
                    self._id,
                    temp,
                    self._status[SETPOINT_STATE][TARGET_TEMPERATURE]
                )
            else:
                _LOGGER.debug(
                    "target_temperature(%s) = %s, via heuristics "
                    "(via api = %s)",
                    self._id,
                    temp,
                    self._status[SETPOINT_STATE][TARGET_TEMPERATURE]
                    )

        else:
            _LOGGER.debug("target_temperature(%s) = %s", self._id, temp)
        return temp

    @property
    def target_temperature_step(self):
        """Return the step of setpont (target temp) of a zone.

        Only applies to heating zones, not DHW controllers (boilers).
        """
#       step = self._config[SETPOINT_CAPABILITIES]['valueResolution']
        step = PRECISION_HALVES
#       _LOGGER.debug("target_temperature_step(%s) = %s", self._id, step)
        return step


class EvoBoiler(EvoSlaveEntity):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def _set_dhw_state(self, state=None, mode=None, until=None):
        """Set the new state of a DHW controller.

        Turn the DHW on/off for an hour, until next setpoint, or indefinitely.
        The setpoint feature requires 'use_schedules' = True.

        Keyword arguments can be:
          - state  = "On" | "Off" (no default)
          - mode  = "TemporaryOverride" (default) | "PermanentOverride"
          - until.strftime('%Y-%m-%dT%H:%M:%SZ') is:
            - +1h for TemporaryOverride if not using schedules
            - next setpoint for TemporaryOverride if using schedules
            - ignored for PermanentOverride
        """
        _LOGGER.debug(
            "DHW._set_dhw_state(%s): state=%s, mode=%s, until=%s",
            self._id,
            state,
            mode,
            until
        )

        if state is None:
            state = self._status['stateStatus']['state']
        if mode is None:
            mode = EVO_TEMPOVER

        if mode != EVO_TEMPOVER:
            until = None
        else:
            if until is None:
                if self._params[CONF_USE_SCHEDULES]:
                    until = self._next_switchpoint_time
                else:
                    until = datetime.now() + timedelta(hours=1)

        if until is not None:
            until = until.strftime('%Y-%m-%dT%H:%M:%SZ')

        data = {'State': state, 'Mode': mode, 'UntilTime': until}

        _LOGGER.debug(
            "_set_dhw_state(%s): API call [1 request(s)]: dhw._set_dhw(%s)...",
            self._id,
            data
        )

        try:
            self._obj._set_dhw(data)                                            # noqa: E501; pylint: disable=protected-access

        except requests.exceptions.HTTPError as err:
            self._handle_requests_exceptions("HTTPError", err)

        if self._params[CONF_USE_HEURISTICS]:
            self._status['stateStatus']['state'] = state
            self._status['stateStatus']['mode'] = mode
            self.async_schedule_update_ha_state(force_refresh=False)

    @property
    def state(self):
        """Return the state of a DHW controller.

        Reportable State can be:
          - On, working to raise current temp until equal to target temp
          - Off, current temp is ignored
          - Away, Off regardless of scheduled state
        """
        domain_data = self.hass.data[DATA_EVOHOME]
        dhw_state = self._status['stateStatus']['state']

        if dhw_state == DHW_STATES[STATE_ON]:
            state = STATE_ON
        elif dhw_state == DHW_STATES[STATE_OFF]:
            state = STATE_OFF
        else:
            state = STATE_UNKNOWN

        # Optionally, use heuristics to override reported state (mode)
        if self._params[CONF_USE_HEURISTICS]:
            tcs_op_mode = domain_data['status']['systemModeStatus']['mode']
            if tcs_op_mode == EVO_AWAY:
                state = EVO_AWAY

            if DHW_STATES[state] != self._status['stateStatus']['state']:
                _LOGGER.warning(
                    "state(%s) = %s, via heuristics (via api = %s)",
                    self._id,
                    state,
                    self._status['stateStatus']['state']
                )
            else:
                _LOGGER.debug(
                    "state(%s) = %s, via heuristics (via api = %s)",
                    self._id,
                    state,
                    self._status['stateStatus']['state']
                )
        else:
            _LOGGER.debug("state(%s) = %s", self._id, state)
        return state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        # this is needed for EvoBoiler(Entity) class to show a graph of temp
        return TEMP_CELSIUS

    @property
    def is_on(self):
        """Return True if DHW is on (albeit regulated by thermostat)."""
        is_on = (self.state == DHW_STATES[STATE_ON])

        _LOGGER.debug("is_on(%s) = %s", self._id, is_on)
        return is_on

    def async_turn_on(self, mode, until):
        """Provide an async wrapper for self.turn_on().

        Note the underlying method is not asyncio-friendly.
        """
        return self.hass.async_add_job(self.turn_on, mode, until)

    def turn_on(self, mode=EVO_TEMPOVER, until=None):
        """Turn DHW on for an hour, until next setpoint, or indefinitely."""
        _LOGGER.debug(
            "turn_on(%s, mode=%s, until=%s)",
            self._id,
            mode,
            until
        )

        self._set_dhw_state(DHW_STATES[STATE_ON], mode, until)

    def async_turn_off(self, mode, until):
        """Provide an async wrapper for self.turn_off().

        Note the underlying method is not asyncio-friendly.
        """
        return self.hass.async_add_job(self.turn_off, mode, until)

    def turn_off(self, mode=EVO_TEMPOVER, until=None):
        """Turn DHW off for an hour, until next setpoint, or indefinitely."""
        _LOGGER.debug(
            "turn_off(%s, mode=%s, until=%s)",
            self._id,
            mode,
            until
        )

        self._set_dhw_state(DHW_STATES[STATE_OFF], mode, until)

    def async_set_operation_mode(self, operation_mode):
        """Provide an async wrapper for self.set_operation_mode().

        Note the underlying method is not asyncio-friendly.
        """
        return self.hass.async_add_job(self.set_operation_mode, operation_mode)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode for a DHW controller."""
        _LOGGER.debug(
            "set_operation_mode(%s, operation_mode=%s)",
            self._id,
            operation_mode
        )

# FollowSchedule - return to scheduled target temp (indefinitely)
        if operation_mode == EVO_FOLLOW:
            state = ''
        else:
            state = self._status['stateStatus']['state']

# PermanentOverride - override target temp indefinitely
# TemporaryOverride - override target temp, for a period of time
        if operation_mode == EVO_TEMPOVER:
            if self._params[CONF_USE_SCHEDULES]:
                until = self._next_switchpoint_time
            else:
                until = datetime.now() + timedelta(hours=1)

            until = until.strftime('%Y-%m-%dT%H:%M:%SZ')

        else:
            until = None

        self._set_dhw_state(state, operation_mode, until)
