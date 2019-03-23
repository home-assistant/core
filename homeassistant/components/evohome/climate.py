"""Support for Climate devices of (EMEA/EU-based) Honeywell evohome systems."""
from datetime import datetime, timedelta
import logging

from requests.exceptions import HTTPError

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_ECO, STATE_MANUAL, SUPPORT_AWAY_MODE, SUPPORT_ON_OFF,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    CONF_SCAN_INTERVAL, HTTP_TOO_MANY_REQUESTS, PRECISION_HALVES, STATE_OFF,
    TEMP_CELSIUS)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, dispatcher_send)

from . import (
    CONF_LOCATION_IDX, DATA_EVOHOME, DISPATCHER_EVOHOME, EVO_CHILD, EVO_PARENT,
    GWS, SCAN_INTERVAL_DEFAULT, TCS)

_LOGGER = logging.getLogger(__name__)

# The Controller's opmode/state and the zone's (inherited) state
EVO_RESET = 'AutoWithReset'
EVO_AUTO = 'Auto'
EVO_AUTOECO = 'AutoWithEco'
EVO_AWAY = 'Away'
EVO_DAYOFF = 'DayOff'
EVO_CUSTOM = 'Custom'
EVO_HEATOFF = 'HeatingOff'

# These are for Zones' opmode, and state
EVO_FOLLOW = 'FollowSchedule'
EVO_TEMPOVER = 'TemporaryOverride'
EVO_PERMOVER = 'PermanentOverride'

# For the Controller. NB: evohome treats Away mode as a mode in/of itself,
# where HA considers it to 'override' the exising operating mode
TCS_STATE_TO_HA = {
    EVO_RESET: STATE_AUTO,
    EVO_AUTO: STATE_AUTO,
    EVO_AUTOECO: STATE_ECO,
    EVO_AWAY: STATE_AUTO,
    EVO_DAYOFF: STATE_AUTO,
    EVO_CUSTOM: STATE_AUTO,
    EVO_HEATOFF: STATE_OFF
}
HA_STATE_TO_TCS = {
    STATE_AUTO: EVO_AUTO,
    STATE_ECO: EVO_AUTOECO,
    STATE_OFF: EVO_HEATOFF
}
TCS_OP_LIST = list(HA_STATE_TO_TCS)

# the Zones' opmode; their state is usually 'inherited' from the TCS
EVO_FOLLOW = 'FollowSchedule'
EVO_TEMPOVER = 'TemporaryOverride'
EVO_PERMOVER = 'PermanentOverride'

# for the Zones...
ZONE_STATE_TO_HA = {
    EVO_FOLLOW: STATE_AUTO,
    EVO_TEMPOVER: STATE_MANUAL,
    EVO_PERMOVER: STATE_MANUAL
}
HA_STATE_TO_ZONE = {
    STATE_AUTO: EVO_FOLLOW,
    STATE_MANUAL: EVO_PERMOVER
}
ZONE_OP_LIST = list(HA_STATE_TO_ZONE)


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the evohome Controller, and its Zones, if any."""
    evo_data = hass.data[DATA_EVOHOME]

    client = evo_data['client']
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]

    # evohomeclient has exposed no means of accessing non-default location
    # (i.e. loc_idx > 0) other than using a protected member, such as below
    tcs_obj_ref = client.locations[loc_idx]._gateways[0]._control_systems[0]  # noqa E501; pylint: disable=protected-access

    _LOGGER.debug(
        "Found Controller, id=%s [%s], name=%s (location_idx=%s)",
        tcs_obj_ref.systemId, tcs_obj_ref.modelType, tcs_obj_ref.location.name,
        loc_idx)

    controller = EvoController(evo_data, client, tcs_obj_ref)
    zones = []

    for zone_idx in tcs_obj_ref.zones:
        zone_obj_ref = tcs_obj_ref.zones[zone_idx]
        _LOGGER.debug(
            "Found Zone, id=%s [%s], name=%s",
            zone_obj_ref.zoneId, zone_obj_ref.zone_type, zone_obj_ref.name)
        zones.append(EvoZone(evo_data, client, zone_obj_ref))

    entities = [controller] + zones

    async_add_entities(entities, update_before_add=False)


class EvoClimateDevice(ClimateDevice):
    """Base for a Honeywell evohome Climate device."""

    # pylint: disable=no-member

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome entity."""
        self._client = client
        self._obj = obj_ref

        self._params = evo_data['params']
        self._timers = evo_data['timers']
        self._status = {}

        self._available = False  # should become True after first update()

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        async_dispatcher_connect(self.hass, DISPATCHER_EVOHOME, self._connect)

    @callback
    def _connect(self, packet):
        if packet['to'] & self._type and packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    def _handle_requests_exceptions(self, err):
        if err.response.status_code == HTTP_TOO_MANY_REQUESTS:
            # execute a backoff: pause, and also reduce rate
            old_interval = self._params[CONF_SCAN_INTERVAL]
            new_interval = min(old_interval, SCAN_INTERVAL_DEFAULT) * 2
            self._params[CONF_SCAN_INTERVAL] = new_interval

            _LOGGER.warning(
                "API rate limit has been exceeded. Suspending polling for %s "
                "seconds, and increasing '%s' from %s to %s seconds",
                new_interval * 3, CONF_SCAN_INTERVAL, old_interval,
                new_interval)

            self._timers['statusUpdated'] = datetime.now() + new_interval * 3

        else:
            raise err  # we dont handle any other HTTPErrors

    @property
    def name(self) -> str:
        """Return the name to use in the frontend UI."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend UI."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the evohome Climate device.

        This is state data that is not available otherwise, due to the
        restrictions placed upon ClimateDevice properties, etc. by HA.
        """
        return {'status': self._status}

    @property
    def available(self) -> bool:
        """Return True if the device is currently available."""
        return self._available

    @property
    def supported_features(self):
        """Get the list of supported features of the device."""
        return self._supported_features

    @property
    def operation_list(self):
        """Return the list of available operations."""
        return self._operation_list

    @property
    def temperature_unit(self):
        """Return the temperature unit to use in the frontend UI."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return the temperature precision to use in the frontend UI."""
        return PRECISION_HALVES


class EvoZone(EvoClimateDevice):
    """Base for a Honeywell evohome Zone device."""

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome Zone."""
        super().__init__(evo_data, client, obj_ref)

        self._id = obj_ref.zoneId
        self._name = obj_ref.name
        self._icon = "mdi:radiator"
        self._type = EVO_CHILD

        for _zone in evo_data['config'][GWS][0][TCS][0]['zones']:
            if _zone['zoneId'] == self._id:
                self._config = _zone
                break
        self._status = {}

        self._operation_list = ZONE_OP_LIST
        self._supported_features = \
            SUPPORT_OPERATION_MODE | \
            SUPPORT_TARGET_TEMPERATURE | \
            SUPPORT_ON_OFF

    @property
    def min_temp(self):
        """Return the minimum target temperature of a evohome Zone.

        The default is 5 (in Celsius), but it is configurable within 5-35.
        """
        return self._config['setpointCapabilities']['minHeatSetpoint']

    @property
    def max_temp(self):
        """Return the minimum target temperature of a evohome Zone.

        The default is 35 (in Celsius), but it is configurable within 5-35.
        """
        return self._config['setpointCapabilities']['maxHeatSetpoint']

    @property
    def target_temperature(self):
        """Return the target temperature of the evohome Zone."""
        return self._status['setpointStatus']['targetHeatTemperature']

    @property
    def current_temperature(self):
        """Return the current temperature of the evohome Zone."""
        return self._status['temperatureStatus']['temperature']

    @property
    def current_operation(self):
        """Return the current operating mode of the evohome Zone.

        The evohome Zones that are in 'FollowSchedule' mode inherit their
        actual operating mode from the Controller.
        """
        evo_data = self.hass.data[DATA_EVOHOME]

        system_mode = evo_data['status']['systemModeStatus']['mode']
        setpoint_mode = self._status['setpointStatus']['setpointMode']

        if setpoint_mode == EVO_FOLLOW:
            # then inherit state from the controller
            if system_mode == EVO_RESET:
                current_operation = TCS_STATE_TO_HA.get(EVO_AUTO)
            else:
                current_operation = TCS_STATE_TO_HA.get(system_mode)
        else:
            current_operation = ZONE_STATE_TO_HA.get(setpoint_mode)

        return current_operation

    @property
    def is_on(self) -> bool:
        """Return True if the evohome Zone is off.

        A Zone is considered off if its target temp is set to its minimum, and
        it is not following its schedule (i.e. not in 'FollowSchedule' mode).
        """
        is_off = \
            self.target_temperature == self.min_temp and \
            self._status['setpointStatus']['setpointMode'] == EVO_PERMOVER
        return not is_off

    def _set_temperature(self, temperature, until=None):
        """Set the new target temperature of a Zone.

        temperature is required, until can be:
          - strftime('%Y-%m-%dT%H:%M:%SZ') for TemporaryOverride, or
          - None for PermanentOverride (i.e. indefinitely)
        """
        try:
            self._obj.set_temperature(temperature, until)
        except HTTPError as err:
            self._handle_exception("HTTPError", str(err))  # noqa: E501; pylint: disable=no-member

    def set_temperature(self, **kwargs):
        """Set new target temperature, indefinitely."""
        self._set_temperature(kwargs['temperature'], until=None)

    def turn_on(self):
        """Turn the evohome Zone on.

        This is achieved by setting the Zone to its 'FollowSchedule' mode.
        """
        self._set_operation_mode(EVO_FOLLOW)

    def turn_off(self):
        """Turn the evohome Zone off.

        This is achieved by setting the Zone to its minimum temperature,
        indefinitely (i.e. 'PermanentOverride' mode).
        """
        self._set_temperature(self.min_temp, until=None)

    def set_operation_mode(self, operation_mode):
        """Set an operating mode for a Zone.

        Currently limited to 'Auto' & 'Manual'. If 'Off' is needed, it can be
        enabled via turn_off method.

        NB: evohome Zones do not have an operating mode as understood by HA.
        Instead they usually 'inherit' an operating mode from their controller.

        More correctly, these Zones are in a follow mode, 'FollowSchedule',
        where their setpoint temperatures are a function of their schedule, and
        the Controller's operating_mode, e.g. Economy mode is their scheduled
        setpoint less (usually) 3C.

        Thus, you cannot set a Zone to Away mode, but the location (i.e. the
        Controller) is set to Away and each Zones's setpoints are adjusted
        accordingly to some lower temperature.

        However, Zones can override these setpoints, either for a specified
        period of time, 'TemporaryOverride', after which they will revert back
        to 'FollowSchedule' mode, or indefinitely, 'PermanentOverride'.
        """
        self._set_operation_mode(HA_STATE_TO_ZONE.get(operation_mode))

    def _set_operation_mode(self, operation_mode):
        if operation_mode == EVO_FOLLOW:
            try:
                self._obj.cancel_temp_override(self._obj)
            except HTTPError as err:
                self._handle_exception("HTTPError", str(err))  # noqa: E501; pylint: disable=no-member

        elif operation_mode == EVO_TEMPOVER:
            _LOGGER.error(
                "_set_operation_mode(op_mode=%s): mode not yet implemented",
                operation_mode
            )

        elif operation_mode == EVO_PERMOVER:
            self._set_temperature(self.target_temperature, until=None)

        else:
            _LOGGER.error(
                "_set_operation_mode(op_mode=%s): mode not valid",
                operation_mode
            )

    @property
    def should_poll(self) -> bool:
        """Return False as evohome child devices should never be polled.

        The evohome Controller will inform its children when to update().
        """
        return False

    def update(self):
        """Process the evohome Zone's state data."""
        evo_data = self.hass.data[DATA_EVOHOME]

        for _zone in evo_data['status']['zones']:
            if _zone['zoneId'] == self._id:
                self._status = _zone
                break

        self._available = True


class EvoController(EvoClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.  It is also a Climate device.
    """

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome Controller (hub)."""
        super().__init__(evo_data, client, obj_ref)

        self._id = obj_ref.systemId
        self._name = '_{}'.format(obj_ref.location.name)
        self._icon = "mdi:thermostat"
        self._type = EVO_PARENT

        self._config = evo_data['config'][GWS][0][TCS][0]
        self._status = evo_data['status']
        self._timers['statusUpdated'] = datetime.min

        self._operation_list = TCS_OP_LIST
        self._supported_features = \
            SUPPORT_OPERATION_MODE | \
            SUPPORT_AWAY_MODE

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the evohome Controller.

        This is state data that is not available otherwise, due to the
        restrictions placed upon ClimateDevice properties, etc. by HA.
        """
        status = dict(self._status)

        if 'zones' in status:
            del status['zones']
        if 'dhw' in status:
            del status['dhw']

        return {'status': status}

    @property
    def current_operation(self):
        """Return the current operating mode of the evohome Controller."""
        return TCS_STATE_TO_HA.get(self._status['systemModeStatus']['mode'])

    @property
    def min_temp(self):
        """Return the minimum target temperature of a evohome Controller.

        Although evohome Controllers do not have a minimum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        return 5

    @property
    def max_temp(self):
        """Return the minimum target temperature of a evohome Controller.

        Although evohome Controllers do not have a maximum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        return 35

    @property
    def target_temperature(self):
        """Return the average target temperature of the Heating/DHW zones.

        Although evohome Controllers do not have a target temp, one is
        expected by the HA schema.
        """
        temps = [zone['setpointStatus']['targetHeatTemperature']
                 for zone in self._status['zones']]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        return avg_temp

    @property
    def current_temperature(self):
        """Return the average current temperature of the Heating/DHW zones.

        Although evohome Controllers do not have a target temp, one is
        expected by the HA schema.
        """
        tmp_list = [x for x in self._status['zones']
                    if x['temperatureStatus']['isAvailable'] is True]
        temps = [zone['temperatureStatus']['temperature'] for zone in tmp_list]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        return avg_temp

    @property
    def is_on(self) -> bool:
        """Return True as evohome Controllers are always on.

        For example, evohome Controllers have a 'HeatingOff' mode, but even
        then the DHW would remain on.
        """
        return True

    @property
    def is_away_mode_on(self) -> bool:
        """Return True if away mode is on."""
        return self._status['systemModeStatus']['mode'] == EVO_AWAY

    def turn_away_mode_on(self):
        """Turn away mode on.

        The evohome Controller will not remember is previous operating mode.
        """
        self._set_operation_mode(EVO_AWAY)

    def turn_away_mode_off(self):
        """Turn away mode off.

        The evohome Controller can not recall its previous operating mode (as
        intimated by the HA schema), so this method is achieved by setting the
        Controller's mode back to Auto.
        """
        self._set_operation_mode(EVO_AUTO)

    def _set_operation_mode(self, operation_mode):
        try:
            self._obj._set_status(operation_mode)  # noqa: E501; pylint: disable=protected-access
        except HTTPError as err:
            self._handle_requests_exceptions(err)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        Currently limited to 'Auto', 'AutoWithEco' & 'HeatingOff'. If 'Away'
        mode is needed, it can be enabled via turn_away_mode_on method.
        """
        self._set_operation_mode(HA_STATE_TO_TCS.get(operation_mode))

    @property
    def should_poll(self) -> bool:
        """Return True as the evohome Controller should always be polled."""
        return True

    def update(self):
        """Get the latest state data of the entire evohome Location.

        This includes state data for the Controller and all its child devices,
        such as the operating mode of the Controller and the current temp of
        its children (e.g. Zones, DHW controller).
        """
        # should the latest evohome state data be retreived this cycle?
        timeout = datetime.now() + timedelta(seconds=55)
        expired = timeout > self._timers['statusUpdated'] + \
            self._params[CONF_SCAN_INTERVAL]

        if not expired:
            return

        # Retrieve the latest state data via the client API
        loc_idx = self._params[CONF_LOCATION_IDX]

        try:
            self._status.update(
                self._client.locations[loc_idx].status()[GWS][0][TCS][0])
        except HTTPError as err:  # check if we've exceeded the api rate limit
            self._handle_requests_exceptions(err)
        else:
            self._timers['statusUpdated'] = datetime.now()
            self._available = True

        _LOGGER.debug("Status = %s", self._status)

        # inform the child devices that state data has been updated
        pkt = {'sender': 'controller', 'signal': 'refresh', 'to': EVO_CHILD}
        dispatcher_send(self.hass, DISPATCHER_EVOHOME, pkt)
