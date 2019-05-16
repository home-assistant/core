"""Support for Climate devices of (EMEA/EU-based) Honeywell evohome systems."""
from datetime import datetime, timedelta
import logging
from typing import Any, Awaitable, Dict, Optional, List

import requests.exceptions

import evohomeclient2

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF,
    PRESET_ECO, PRESET_AWAY, PRESET_HOME, PRESET_SLEEP,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE, SUPPORT_CURRENT_HVAC,
    CURRENT_HVAC_OFF, CURRENT_HVAC_HEAT,
)
from homeassistant.const import (
    CONF_SCAN_INTERVAL, STATE_OFF,)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import dispatcher_send

from . import (
    EvoDevice,
    CONF_LOCATION_IDX)
from .const import (
    DATA_EVOHOME, DOMAIN, GWS, TCS)

_LOGGER = logging.getLogger(__name__)

# The Controller's opmode/state and the zone's (inherited) state
EVO_RESET = 'AutoWithReset'
EVO_AUTO = 'Auto'
EVO_AUTOECO = 'AutoWithEco'
EVO_AWAY = 'Away'
EVO_DAYOFF = 'DayOff'
EVO_CUSTOM = 'Custom'
EVO_HEATOFF = 'HeatingOff'

# For the Controller. NB: evohome treats Away mode as a mode in/of itself,
# where HA considers it to 'override' the exising operating mode
TCS_STATE_TO_HA = {
    EVO_RESET: HVAC_MODE_AUTO,
    EVO_AUTO: HVAC_MODE_AUTO,
    EVO_AUTOECO: PRESET_ECO,
    EVO_AWAY: PRESET_AWAY,
    EVO_DAYOFF: PRESET_HOME,
    EVO_CUSTOM: HVAC_MODE_AUTO,
    EVO_HEATOFF: HVAC_MODE_OFF
}
HA_PRESET_TO_TCS = {
    HVAC_MODE_AUTO: EVO_AUTO,
    PRESET_ECO: EVO_AUTOECO,
    STATE_OFF: EVO_HEATOFF
}

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
HA_MODE_TO_ZONE = {
    HVAC_MODE_AUTO: EVO_FOLLOW,
    HVAC_MODE_HEAT: EVO_PERMOVER
}


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):

    """Create the evohome Controller, and its Zones, if any."""
    _LOGGER.warn("setup_platform(CLIMATE): started")                             # TODO: delete me

    evo_data = hass.data[DATA_EVOHOME]

    client = evo_data['client']
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]

    # evohomeclient has exposed no means of accessing non-default location
    # (i.e. loc_idx > 0) other than using a protected member, such as below
    evo_tcs = client.locations[loc_idx]._gateways[0]._control_systems[0]  # noqa: E501; pylint: disable=protected-access

    _LOGGER.debug(
        "Found Controller, id=%s [%s], name=%s (location_idx=%s)",
        evo_tcs.systemId, evo_tcs.modelType, evo_tcs.location.name,
        loc_idx)

    controller = EvoController(evo_data, client, evo_tcs)
    zones = []

    for zone_idx in evo_tcs.zones:
        evo_zone_ref = evo_tcs.zones[zone_idx]
        _LOGGER.debug(
            "Found Zone, id=%s [%s], name=%s",
            evo_zone_ref.zoneId, evo_zone_ref.zone_type, evo_zone_ref.name)
        zones.append(EvoZone(evo_data, client, evo_zone_ref))

    entities = [controller] + zones

    async_add_entities(entities, update_before_add=False)


class EvoZone(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome Zone device."""

    def __init__(self, evo_data, client, evo_zone_ref):
        """Initialize the evohome Zone."""
        super().__init__(evo_data, client, evo_zone_ref)

        self._id = evo_zone_ref.zoneId
        self._name = evo_zone_ref.name
        self._icon = "mdi:radiator"

        for _zone in evo_data['config'][GWS][0][TCS][0]['zones']:
            if _zone['zoneId'] == self._id:
                self._config = _zone
                break

        self._operation_list = list(HA_STATE_TO_ZONE)
        self._supported_features = \
            SUPPORT_OPERATION_MODE | \
            SUPPORT_TARGET_TEMPERATURE | \
            SUPPORT_ON_OFF

# REMOVE: These are from the ToggleEntity class
    @property
    def XXX_is_on(self) -> bool:
        """Return True if the evohome Zone is off.

        A Zone is considered off if its target temp is set to its minimum, and
        it is not following its schedule (i.e. not in 'FollowSchedule' mode).
        """
        is_off = \
            self.target_temperature == self.min_temp and \
            self._status['setpointStatus']['setpointMode'] == EVO_PERMOVER
        # _LOGGER.warn("is_on(%s): %s", self._id, not is_off)
        return not is_off

    def XXX_turn_on(self):
        """Turn the evohome Zone on.

        This is achieved by setting the Zone to its 'FollowSchedule' mode.
        """
        # _LOGGER.warn("is_on(%s)", self._id)
        self._set_operation_mode(EVO_FOLLOW)

    def XXX_turn_off(self):
        """Turn the evohome Zone off.

        This is achieved by setting the Zone to its minimum temperature,
        indefinitely (i.e. 'PermanentOverride' mode).
        """
        # _LOGGER.warn("turn_off(%s)", self._id)
        self._set_temperature(self.min_temp, until=None)


# These properties, methods are from the ClimateDevice class
    @property  # ClimateDevice
    def hvac_state(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        # _LOGGER.warn("hvac_state(%s): %s", self._id, HVAC_MODE_AUTO)
        return HVAC_MODE_AUTO

    @property  # ClimateDevice
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        # _LOGGER.warn("hvac_modes(%s): %s", self._id, HA_MODES_FOR_ZONE)
        return HA_MODES_FOR_ZONE

    @property  # ClimateDevice
    def current_hvac(self) -> Optional[str]:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        # _LOGGER.warn("current_hvac(%s): %s", self._id, HVAC_MODE_AUTO)
        return HVAC_MODE_AUTO

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature of the evohome Zone."""
        # _LOGGER.warn("current_temperature(%s): XX", self._id)
        return (self._status['temperatureStatus']['temperature']
                if self._status['temperatureStatus']['isAvailable'] else None)

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature of the evohome Zone."""
        # _LOGGER.warn("target_temperature(%s): XX", self._id)
        return self._status['setpointStatus']['targetHeatTemperature']

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        _LOGGER.warn("preset_mode(%s): %s", self._id, 'auto')
        return 'auto'

    @property  # ClimateDevice
    def preset_list(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        _LOGGER.warn("preset_list(%s): %s", self._id, HA_PRESETS_FOR_ZONE)
        return HA_PRESETS_FOR_ZONE

    @property  # ClimateDevice
    def min_temp(self) -> float:
        """Return the minimum target temperature of a evohome Zone.

        The default is 5, but it is configurable within 5-35 (in Celsius).
        """
        # _LOGGER.warn("min_temp(%s): XX", self._id)
        return self._config['setpointCapabilities']['minHeatSetpoint']

    @property  # ClimateDevice
    def max_temp(self) -> float:
        """Return the maximum target temperature of a evohome Zone.

        The default is 35, but it is configurable within 5-35 (in Celsius).
        """
        # _LOGGER.warn("max_temp(%s): XX", self._id)
        return self._config['setpointCapabilities']['maxHeatSetpoint']




    @property
    def XXX_current_operation(self):
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
            current_operation = ZONE_MODE_TO_HA.get(setpoint_mode)

        return current_operation

    def _set_temperature(self, temperature, until=None):
        """Set the new target temperature of a Zone.

        temperature is required, until can be:
          - strftime('%Y-%m-%dT%H:%M:%SZ') for TemporaryOverride, or
          - None for PermanentOverride (i.e. indefinitely)
        """
        try:
            self._evo_device.set_temperature(temperature, until)
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)

    def set_temperature(self, **kwargs):
        """Set new target temperature, indefinitely."""
        self._set_temperature(kwargs['temperature'], until=None)

    def _set_operation_mode(self, operation_mode):
        if operation_mode == EVO_FOLLOW:
            try:
                self._evo_device.cancel_temp_override()
            except (requests.exceptions.RequestException,
                    evohomeclient2.AuthenticationError) as err:
                self._handle_exception(err)

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

    def XXX_set_operation_mode(self, operation_mode):
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
        self._set_operation_mode(HA_STATE_TO_ZONE[operation_mode])

    async def async_update(self):
        """Process the evohome Zone's state data."""
        _LOGGER.debug("update(%s)", self._id)

        evo_data = self.hass.data[DATA_EVOHOME]

        for _zone in evo_data['status']['zones']:
            if _zone['zoneId'] == self._id:
                self._status = _zone
                break

        self._available = True


class EvoController(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.  It is also a Climate device.
    """

    def __init__(self, evo_data, client, evo_tcs):
        """Initialize the evohome Controller (hub)."""
        super().__init__(evo_data, client, evo_tcs)

        self._id = evo_tcs.systemId
        self._name = '_{}'.format(evo_tcs.location.name)
        self._icon = "mdi:thermostat"

        self._config = evo_data['config'][GWS][0][TCS][0]
        self._status = evo_data['status']
        self._timers['statusUpdated'] = datetime.min

        self._operation_list = list(HA_STATE_TO_TCS)
        self._supported_features = \
            SUPPORT_OPERATION_MODE | \
            SUPPORT_AWAY_MODE

    @callback
    def _refresh(self, packet):
        if packet['signal'] == 'first_update':
            self.schedule_update_ha_state(force_refresh=True)

    @property
    def should_poll(self) -> bool:
        """Only the Controller should be polled."""
        _LOGGER.warn("should_poll(%s)=%s", self._id, True)
        return True

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the evohome Controller.

    def update(self):
        """Get the latest state data of the entire evohome Location.

        This includes state data for the Controller and all its child devices,
        such as the operating mode of the Controller and the current temp of
        its children (e.g. Zones, DHW controller).
        """
        _LOGGER.warn("update(TCS=%s): XX", self._id)
        # should the latest evohome state data be retreived this cycle?
        timeout = datetime.now() + timedelta(seconds=55)
        expired = timeout > self._timers['statusUpdated'] + \
            self._params[CONF_SCAN_INTERVAL]

        if not expired:
            return

        # Retrieve the latest state data via the client API
        loc_idx = self._params[CONF_LOCATION_IDX]

        try:  # TODO: use evo_data['status'] instead of self._status where possible
            self._status.update(
                self._client.locations[loc_idx].status()[GWS][0][TCS][0])
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)
        else:
            self._timers['statusUpdated'] = datetime.now()
            self._available = True

        _LOGGER.debug("Status = %s", self._status)

        # inform the child devices that state data has been updated
        dispatcher_send(self.hass, DOMAIN, {'signal': 'refresh'})


# These properties, methods are from the Entity class
    @property  # Entity
    def should_poll(self) -> bool:
        """Only the Evohome Controller should be polled."""
        return True

    @property
    def device_state_attributes(self):
        """Return the device state attributes of the evohome Controller."""
        status = dict(self._status)

        if 'zones' in status:
            del status['zones']
        if 'dhw' in status:
            del status['dhw']

        # _LOGGER.warn("device_state_attributes(TCS=%s): %s", self._id, {'status': status})
        return {'status': status}


# REMOVE: These are from the ToggleEntity class
    @property
    def XXX_is_on(self) -> bool:
        """Return True as evohome Controllers are always on.

        For example, evohome Controllers have a 'HeatingOff' mode, but even
        then the DHW would remain on.
        """
        return True


# These properties, methods are from the ClimateDevice class
    @property  # ClimateDevice
    def hvac_state(self) -> str:
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        _LOGGER.warn("hvac_state(TCS=%s): %s", self._id, HVAC_MODE_AUTO)
        return HVAC_MODE_AUTO

    @property  # ClimateDevice
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        _LOGGER.warn("hvac_modes(TCS=%s): %s", self._id, HA_MODES_FOR_TCS)
        return HA_MODES_FOR_TCS

    @property  # ClimateDevice
    def current_hvac(self) -> Optional[str]:
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self._status['systemModeStatus']['mode'] == EVO_HEATOFF:
            current_hvac = CURRENT_HVAC_OFF
        else:
            current_hvac = CURRENT_HVAC_HEAT
        _LOGGER.warn("current_hvac(TCS=%s): %s", self._id, current_hvac)
        return current_hvac

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the average current temperature of the Heating/DHW zones.

        Although evohome Controllers do not have a target temp, one is
        expected by the HA schema.
        """
        tmp_list = [x for x in self._status['zones']
                    if x['temperatureStatus']['isAvailable']]
        temps = [zone['temperatureStatus']['temperature'] for zone in tmp_list]

        avg_temp = round(sum(temps) / len(temps), 1) if temps else None
        # _LOGGER.warn("current_temperature(TCS=%s): %s", self._id, avg_temp)
        return avg_temp

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        _LOGGER.warn("preset_mode(TCS=%s): %s", self._id, PRESET_ECO)
        return PRESET_ECO

    @property  # ClimateDevice
    def preset_list(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        _LOGGER.warn("preset_list(TCS=%s): %s", self._id, HA_PRESETS_FOR_TCS)
        return HA_PRESETS_FOR_TCS

    @property  # ClimateDevice
    def min_temp(self) -> float:
        """Return the minimum target temperature of a evohome Controller.

        Although evohome Controllers do not have a minimum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        # _LOGGER.warn("min_temp(TCS=%s): %s", self._id, 5)
        return 5

    @property  # ClimateDevice
    def max_temp(self) -> float:
        """Return the maximum target temperature of a evohome Controller.

        Although evohome Controllers do not have a maximum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        # _LOGGER.warn("max_temp(TCS=%s): %s", self._id, 35)
        return 35

    def _set_operation_mode(self, operation_mode):
        try:
            self._evo_device._set_status(operation_mode)  # noqa: E501; pylint: disable=protected-access
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)

    def XXX_set_operation_mode(self, operation_mode):
        """Set new target operation mode for the TCS.

        Currently limited to 'Auto', 'AutoWithEco' & 'HeatingOff'. If 'Away'
        mode is needed, it can be enabled via turn_away_mode_on method.
        """
        self._set_operation_mode(HA_STATE_TO_TCS.get(operation_mode))

    def XXX_turn_away_mode_on(self):
        """Turn away mode on.

        The evohome Controller will not remember is previous operating mode.
        """
        self._set_operation_mode(EVO_AWAY)

    def XXX_turn_away_mode_off(self):
        """Turn away mode off.

        The evohome Controller can not recall its previous operating mode (as
        intimated by the HA schema), so this method is achieved by setting the
        Controller's mode back to Auto.
        """
        self._set_operation_mode(EVO_AUTO)

    def update(self):
        """Get the latest state data of the entire evohome Location.

        This includes state data for the Controller and all its child devices,
        such as the operating mode of the Controller and the current temp of
        its children (e.g. Zones, DHW controller).
        """
        # should the latest evohome state data be retreived this cycle?
        _LOGGER.debug("update(%s)", self._id)

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
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)
        else:
            self._timers['statusUpdated'] = datetime.now()
            self._available = True

        _LOGGER.debug("Status = %s", self._status)

        # inform the child devices that state data has been updated
        dispatcher_send(self.hass, DOMAIN, {'signal': 'refresh'})
