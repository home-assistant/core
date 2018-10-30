"""Support for Honeywell evohome (EMEA/EU-based systems only).

Support for a temperature control system (TCS, controller) with 0+ heating
zones (e.g. TRVs, relays) and, optionally, a DHW controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.evohome/
"""

from datetime import datetime, timedelta
import logging

from requests.exceptions import HTTPError

from homeassistant.components.climate import (
    ClimateDevice,
    STATE_AUTO,
    STATE_ECO,
    STATE_OFF,
    SUPPORT_OPERATION_MODE,
    SUPPORT_AWAY_MODE,
)
from homeassistant.components.evohome import (
    CONF_LOCATION_IDX,
    DATA_EVOHOME,
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
_LOGGER = logging.getLogger(__name__)

# these are for the controller's opmode/state and the zone's state
EVO_RESET = 'AutoWithReset'
EVO_AUTO = 'Auto'
EVO_AUTOECO = 'AutoWithEco'
EVO_AWAY = 'Away'
EVO_DAYOFF = 'DayOff'
EVO_CUSTOM = 'Custom'
EVO_HEATOFF = 'HeatingOff'

EVO_STATE_TO_HA = {
    EVO_RESET: STATE_AUTO,
    EVO_AUTO: STATE_AUTO,
    EVO_AUTOECO: STATE_ECO,
    EVO_AWAY: STATE_AUTO,
    EVO_DAYOFF: STATE_AUTO,
    EVO_CUSTOM: STATE_AUTO,
    EVO_HEATOFF: STATE_OFF
}

HA_STATE_TO_EVO = {
    STATE_AUTO: EVO_AUTO,
    STATE_ECO: EVO_AUTOECO,
    STATE_OFF: EVO_HEATOFF
}

HA_OP_LIST = list(HA_STATE_TO_EVO)

# these are used to help prevent E501 (line too long) violations
GWS = 'gateways'
TCS = 'temperatureControlSystems'

# debug codes - these happen occasionally, but the cause is unknown
EVO_DEBUG_NO_RECENT_UPDATES = '0x01'
EVO_DEBUG_NO_STATUS = '0x02'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create a Honeywell (EMEA/EU) evohome CH/DHW system.

    An evohome system consists of: a controller, with 0-12 heating zones (e.g.
    TRVs, relays) and, optionally, a DHW controller (a HW boiler).

    Here, we add the controller only.
    """
    evo_data = hass.data[DATA_EVOHOME]

    client = evo_data['client']
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]

    # evohomeclient has no defined way of accessing non-default location other
    # than using a protected member, such as below
    tcs_obj_ref = client.locations[loc_idx]._gateways[0]._control_systems[0]    # noqa E501; pylint: disable=protected-access

    _LOGGER.debug(
        "setup_platform(): Found Controller: id: %s [%s], type: %s",
        tcs_obj_ref.systemId,
        tcs_obj_ref.location.name,
        tcs_obj_ref.modelType
    )
    parent = EvoController(evo_data, client, tcs_obj_ref)
    add_entities([parent], update_before_add=True)


class EvoController(ClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.
    """

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome entity.

        Most read-only properties are set here.  So are pseudo read-only,
        for example name (which _could_ change between update()s).
        """
        self.client = client
        self._obj = obj_ref

        self._id = obj_ref.systemId
        self._name = evo_data['config']['locationInfo']['name']

        self._config = evo_data['config'][GWS][0][TCS][0]
        self._params = evo_data['params']
        self._timers = evo_data['timers']

        self._timers['statusUpdated'] = datetime.min
        self._status = {}

        self._available = False  # should become True after first update()

    def _handle_requests_exceptions(self, err):
        # evohomeclient v2 api (>=0.2.7) exposes requests exceptions, incl.:
        # - HTTP_BAD_REQUEST, is usually Bad user credentials
        # - HTTP_TOO_MANY_REQUESTS, is api usuage limit exceeded
        # - HTTP_SERVICE_UNAVAILABLE, is often Vendor's fault

        if err.response.status_code == HTTP_TOO_MANY_REQUESTS:
            # execute a back off: pause, and reduce rate
            old_scan_interval = self._params[CONF_SCAN_INTERVAL]
            new_scan_interval = min(old_scan_interval * 2, SCAN_INTERVAL_MAX)
            self._params[CONF_SCAN_INTERVAL] = new_scan_interval

            _LOGGER.warning(
                "API rate limit has been exceeded: increasing '%s' from %s to "
                "%s seconds, and suspending polling for %s seconds.",
                CONF_SCAN_INTERVAL,
                old_scan_interval,
                new_scan_interval,
                new_scan_interval * 3
            )

            self._timers['statusUpdated'] = datetime.now() + \
                timedelta(seconds=new_scan_interval * 3)

        else:
            raise err

    @property
    def name(self):
        """Return the name to use in the frontend UI."""
        return self._name

    @property
    def available(self):
        """Return True if the device is available.

        All evohome entities are initially unavailable. Once HA has started,
        state data is then retrieved by the Controller, and then the children
        will get a state (e.g. operating_mode, current_temperature).

        However, evohome entities can become unavailable for other reasons.
        """
        return self._available

    @property
    def supported_features(self):
        """Get the list of supported features of the Controller."""
        return SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the controller.

        This is operating mode state data that is not available otherwise, due
        to the restrictions placed upon ClimateDevice properties, etc by HA.
        """
        data = {}
        data['systemMode'] = self._status['systemModeStatus']['mode']
        data['isPermanent'] = self._status['systemModeStatus']['isPermanent']
        if 'timeUntil' in self._status['systemModeStatus']:
            data['timeUntil'] = self._status['systemModeStatus']['timeUntil']
        data['activeFaults'] = self._status['activeFaults']
        return data

    @property
    def operation_list(self):
        """Return the list of available operations."""
        return HA_OP_LIST

    @property
    def current_operation(self):
        """Return the operation mode of the evohome entity."""
        return EVO_STATE_TO_HA.get(self._status['systemModeStatus']['mode'])

    @property
    def target_temperature(self):
        """Return the average target temperature of the Heating/DHW zones."""
        temps = [zone['setpointStatus']['targetHeatTemperature']
                 for zone in self._status['zones']]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        return avg_temp

    @property
    def current_temperature(self):
        """Return the average current temperature of the Heating/DHW zones."""
        tmp_list = [x for x in self._status['zones']
                    if x['temperatureStatus']['isAvailable'] is True]
        temps = [zone['temperatureStatus']['temperature'] for zone in tmp_list]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
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
        """Return the minimum target temp (setpoint) of a evohome entity."""
        return MIN_TEMP

    @property
    def max_temp(self):
        """Return the maximum target temp (setpoint) of a evohome entity."""
        return MAX_TEMP

    @property
    def is_on(self):
        """Return true as evohome controllers are always on.

        Operating modes can include 'HeatingOff', but (for example) DHW would
        remain on.
        """
        return True

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._status['systemModeStatus']['mode'] == EVO_AWAY

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._set_operation_mode(EVO_AWAY)

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._set_operation_mode(EVO_AUTO)

    def _set_operation_mode(self, operation_mode):
        # Set new target operation mode for the TCS.
        _LOGGER.debug(
            "_set_operation_mode(): API call [1 request(s)]: "
            "tcs._set_status(%s)...",
            operation_mode
        )
        try:
            self._obj._set_status(operation_mode)                               # noqa: E501; pylint: disable=protected-access
        except HTTPError as err:
            self._handle_requests_exceptions(err)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        Currently limited to 'Auto', 'AutoWithEco' & 'HeatingOff'. If 'Away'
        mode is needed, it can be enabled via turn_away_mode_on method.
        """
        self._set_operation_mode(HA_STATE_TO_EVO.get(operation_mode))

    def _update_state_data(self, evo_data):
        client = evo_data['client']
        loc_idx = evo_data['params'][CONF_LOCATION_IDX]

        _LOGGER.debug(
            "_update_state_data(): API call [1 request(s)]: "
            "client.locations[loc_idx].status()..."
        )

        try:
            evo_data['status'].update(
                client.locations[loc_idx].status()[GWS][0][TCS][0])
        except HTTPError as err:  # check if we've exceeded the api rate limit
            self._handle_requests_exceptions(err)
        else:
            evo_data['timers']['statusUpdated'] = datetime.now()

        _LOGGER.debug(
            "_update_state_data(): evo_data['status'] = %s",
            evo_data['status']
        )

    def update(self):
        """Get the latest state data of the installation.

        This includes state data for the Controller and its child devices, such
        as the operating_mode of the Controller and the current_temperature
        of its children.

        This is not asyncio-friendly due to the underlying client api.
        """
        evo_data = self.hass.data[DATA_EVOHOME]

        timeout = datetime.now() + timedelta(seconds=55)
        expired = timeout > self._timers['statusUpdated'] + \
            timedelta(seconds=evo_data['params'][CONF_SCAN_INTERVAL])

        if not expired:
            return

        was_available = self._available or \
            self._timers['statusUpdated'] == datetime.min

        self._update_state_data(evo_data)
        self._status = evo_data['status']

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

        no_recent_updates = self._timers['statusUpdated'] < datetime.now() - \
            timedelta(seconds=self._params[CONF_SCAN_INTERVAL] * 3.1)

        if no_recent_updates:
            self._available = False
            debug_code = EVO_DEBUG_NO_RECENT_UPDATES

        elif not self._status:
            # unavailable because no status (but how? other than at startup?)
            self._available = False
            debug_code = EVO_DEBUG_NO_STATUS

        else:
            self._available = True

        if not self._available and was_available:
            # only warn if available went from True to False
            _LOGGER.warning(
                "The entity, %s, has become unavailable, debug code is: %s",
                self._id + " [" + self._name + "]",
                debug_code
            )

        elif self._available and not was_available:
            # this isn't the first re-available (e.g. _after_ STARTUP)
            _LOGGER.debug(
                "The entity, %s, has become available",
                self._id + " [" + self._name + "]"
            )
