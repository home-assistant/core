"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/evohome/
"""

from datetime import datetime, timedelta
import logging
from requests.exceptions import HTTPError

from homeassistant.components.climate import (
    ClimateDevice,
    SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE,
)

from homeassistant.components.evohome import (
    CONF_LOCATION_IDX,
    DATA_EVOHOME,
    DISPATCHER_EVOHOME,
    MAX_TEMP,
    MIN_TEMP,
    SCAN_INTERVAL_MAX
)

from homeassistant.const import (
    CONF_SCAN_INTERVAL,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
    HTTP_TOO_MANY_REQUESTS,
)

from homeassistant.core import callback

_LOGGER = logging.getLogger(__name__)

# Usually, only the controller does client api I/O during update()s to pull
# current state - the exception is when zones pull their own schedules during
# their own update()s. It is safe for them to do so concurrently.
PARALLEL_UPDATES = 0

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
EVO_PARENT = 0x01
EVO_CHILD = 0x02

# these are used to help prevent E501 (line too long) violations
GWS = 'gateways'
TCS = 'temperatureControlSystems'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    An evohome system consists of: a controller, with 0-12 heating zones (e.g.
    TRVs, relays) and, optionally, a DHW controller (a HW boiler).

    Here, we add the controller, and the zones (if there are any).
    """
    client = hass.data[DATA_EVOHOME]['client']
    loc_idx = hass.data[DATA_EVOHOME]['params'][CONF_LOCATION_IDX]

# Collect the (master) controller - evohomeclient has no defined way of
# accessing non-default location other than using the protected member
    tcs_obj_ref = client.locations[loc_idx]._gateways[0]._control_systems[0]    # noqa E501; pylint: disable=protected-access

    _LOGGER.debug(
        "setup_platform(): Found Controller [idx=%s]: id: %s [%s], type: %s",
        loc_idx,
        tcs_obj_ref.systemId,
        tcs_obj_ref.location.name,
        tcs_obj_ref.modelType
    )
    master = EvoController(hass, client, tcs_obj_ref)
    add_entities([master], update_before_add=False)

    return True


class EvoController(ClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.
    """

    def __init__(self, hass, client, obj_ref):
        """Initialize the evohome entity.

        Most read-only properties are set here.  So are pseudo read-only,
        for example name (which _could_ change between update()s).
        """
        # Set the usual object references
        self.hass = hass
        self.client = client
        domain_data = hass.data[DATA_EVOHOME]

        self._obj = obj_ref
        self._type = EVO_PARENT

        # Set the entity's own object reference & identifier
        self._id = obj_ref.systemId

        # Set the entity's configuration shortcut (considered static)
        self._config = domain_data['config'][GWS][0][TCS][0]
        self._params = domain_data['params']

        # Set the entity's name (treated as static vales)
        self._name = domain_data['config']['locationInfo']['name']

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

        # Create a listener for (internal) update packets...
        hass.helpers.dispatcher.dispatcher_connect(
            DISPATCHER_EVOHOME,
            self._connect
        )  # for: def async_dispatcher_connect(signal, target)

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
        if err.response.status_code == HTTP_TOO_MANY_REQUESTS:
            api_rate_limit_exceeded = True
            api_ver = "v2"

        # we can't handle any other exceptions here
        else:
            api_rate_limit_exceeded = False

        # do we need to back off?
        if api_rate_limit_exceeded is True:
            # so increase the scan_interval
            old_scan_interval = self._params[CONF_SCAN_INTERVAL]
            new_scan_interval = min(old_scan_interval * 2, SCAN_INTERVAL_MAX)
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
    def available(self):
        """Return True is the device is available.

        All evohome entities are initially unavailable. Once HA has started,
        state data is then retrieved by the Controller, and then the children
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
            except HTTPError as err:
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

        except HTTPError as err:
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

        This includes state data for the Controller and its child devices, such
        as the operating_mode of the Controller and the current_temperature
        of its children.

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

        was_available = self._available

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

        if not self._available and was_available:
            # only warn if available from False to True
            _LOGGER.warning(
                "The entity, %s, is now unavailable "
                "(i.e. self.available() = False), debug code is: %s",
                self._id + " [" + self._name + "]",
                debug_code
            )

        elif self._available and not was_available and \
                self._timers['statusUpdated'] != datetime.min:
            # this isn't the first re-available (e.g. _after_ STARTUP)
            _LOGGER.debug(
                "The entity, %s, is now available "
                "(i.e. self.available() = True)",
                self._id + " [" + self._name + "]"
            )

        return True
