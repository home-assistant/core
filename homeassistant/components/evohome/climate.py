"""Support for Climate devices of (EMEA/EU-based) Honeywell TCC systems."""
from datetime import datetime, timedelta
import logging

import requests.exceptions

import evohomeclient2

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO, STATE_ECO, STATE_MANUAL, SUPPORT_AWAY_MODE, SUPPORT_ON_OFF,
    SUPPORT_TARGET_TEMPERATURE, HVAC_MODE_OFF)
from homeassistant.const import (
    CONF_SCAN_INTERVAL, PRECISION_HALVES, PRECISION_TENTHS, STATE_OFF,)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util.dt import utc_from_timestamp, utcnow

from . import (EvoDevice, CONF_LOCATION_IDX)
from .const import (
    DOMAIN, GWS, TCS,
    EVO_RESET, EVO_AUTO, EVO_AUTOECO, EVO_AWAY, EVO_DAYOFF, EVO_CUSTOM,
    EVO_HEATOFF, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER)

_LOGGER = logging.getLogger(__name__)

# For the Controller. NB: evohome treats Away mode as a mode in/of itself,
# where HA considers it to 'override' the exising operating mode
TCS_STATE_TO_HA = {
    EVO_RESET: HVAC_MODE_AUTO,
    EVO_AUTO: HVAC_MODE_AUTO,
    EVO_AUTOECO: STATE_ECO,
    EVO_AWAY: HVAC_MODE_AUTO,
    EVO_DAYOFF: HVAC_MODE_AUTO,
    EVO_CUSTOM: HVAC_MODE_AUTO,
    EVO_HEATOFF: HVAC_MODE_OFF
}
HA_STATE_TO_TCS = {
    HVAC_MODE_AUTO: EVO_AUTO,
    STATE_ECO: EVO_AUTOECO,
    HVAC_MODE_OFF: EVO_HEATOFF
}
TCS_STATE_ATTRIBUTES = ['activeFaults', 'systemModeStatus']
# for the Zones...
ZONE_STATE_TO_HA = {
    EVO_FOLLOW: HVAC_MODE_AUTO,
    EVO_TEMPOVER: STATE_MANUAL,
    EVO_PERMOVER: STATE_MANUAL
}
HA_STATE_TO_ZONE = {
    HVAC_MODE_AUTO: EVO_FOLLOW,
    STATE_MANUAL: EVO_PERMOVER
}
ZONE_STATE_ATTRIBUTES = ['activeFaults', 'setpointStatus', 'temperatureStatus']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the evohome Controller, and its Zones, if any."""
    _LOGGER.warn("async_setup_platform(CLIMATE): hass_config=%s", hass_config)   # TODO: delete me

    broker = hass.data[DOMAIN]['broker']
    loc_idx = broker.params[CONF_LOCATION_IDX]

    _LOGGER.debug(
        "Found Controller, id=%s [%s], name=%s (location_idx=%s)",
        broker.tcs.systemId, broker.tcs.modelType, broker.tcs.location.name,
        loc_idx)

    controller = EvoController(broker, broker.tcs)

    zones = []
    for zone_idx in broker.tcs.zones:
        evo_zone = broker.tcs.zones[zone_idx]
        _LOGGER.debug(
            "Found Zone, id=%s [%s], name=%s",
            evo_zone.zoneId, evo_zone.zone_type, evo_zone.name)
        zones.append(EvoZone(broker, evo_zone))

    entities = [controller] + zones

    async_add_entities(entities, update_before_add=True)


class EvoZone(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome Zone device."""

    def __init__(self, evo_broker, evo_device):
        """Initialize the evohome Zone."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.zoneId
        self._name = evo_device.name
        self._icon = "mdi:radiator"

        for _zone in evo_broker.config['zones']:
            if _zone['zoneId'] == self._id:
                self._config = _zone
                break
        _LOGGER.warn("__init__(Zone): self._config = %s", self._config)          # TODO: remove

        self._precision = \
            self._evo_device.setpointCapabilities['valueResolution']
        self._state_attributes = ZONE_STATE_ATTRIBUTES

        self._supported_features = SUPPORT_OPERATION_MODE | \
            SUPPORT_TARGET_TEMPERATURE | \
            SUPPORT_ON_OFF
        self._operation_list = list(HA_STATE_TO_ZONE)

    @property
    def hvac_mode(self):
        """Return the current operating mode of the evohome Zone.

        The evohome Zones that are in 'FollowSchedule' mode inherit their
        actual operating mode from the Controller.
        """
        system_mode = self._evo_tcs.systemModeStatus['mode']
        setpoint_mode = self._evo_device.setpointStatus['setpointMode']

        if system_mode == EVO_HEATOFF or setpoint_mode == EVO_FOLLOW:
            # then inherit state from the controller
            return TCS_STATE_TO_HA.get(system_mode)
        return ZONE_STATE_TO_HA.get(setpoint_mode)

    @property
    def current_temperature(self):
        """Return the current temperature of the evohome Zone."""
        return (self._evo_device.temperatureStatus['temperature']
                if self._evo_device.temperatureStatus['isAvailable'] else None)

    @property
    def target_temperature(self):
        """Return the target temperature of the evohome Zone."""
        return self._evo_device.setpointStatus['targetHeatTemperature']

    @property
    def is_on(self) -> bool:
        """Return True if the evohome Zone is off.

        A Zone is considered off if its target temp is set to its minimum, and
        it is not following its schedule (i.e. not in 'FollowSchedule' mode).
        """
        is_off = \
            self.target_temperature == self.min_temp and \
            self._evo_device.setpointStatus['setpointMode'] == EVO_PERMOVER
        return not is_off

    @property
    def min_temp(self):
        """Return the minimum target temperature of a evohome Zone.

        The default is 5 (in Celsius), but it is configurable within 5-35.
        """
        return self._evo_device.setpointCapabilities['minHeatSetpoint']

    @property
    def max_temp(self):
        """Return the maximum target temperature of a evohome Zone.

        The default is 35 (in Celsius), but it is configurable within 5-35.
        """
        return self._evo_device.setpointCapabilities['maxHeatSetpoint']

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

    def set_hvac_mode(self, hvac_mode):
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
        self._set_operation_mode(HA_STATE_TO_ZONE.get(hvac_mode))

    async def async_update(self):
        """Process the evohome Zone's state data."""
        self._available = self._evo_device.temperatureStatus['isAvailable']

        # _LOGGER.error("dir(self._evo_device) = %s", dir(self._evo_device))
        # _LOGGER.error("%s", self._evo_device.setpointCapabilities['maxHeatSetpoint'])


class EvoController(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome hub/Controller device.

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.  It is also a Climate device.
    """

    def __init__(self, evo_broker, evo_device):
        """Initialize the evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.systemId
        self._name = '_{}'.format(evo_device.location.name)
        self._icon = "mdi:thermostat"

        self._config = dict(evo_broker.config)
        self._config['zones'] = '...'
        if 'dhw' in self._config:
            self._config['dhw'] = '...'
        _LOGGER.warn("__init__(TCS): self._config = %s", self._config)           # TODO: remove

        self._precision = None
        self._state_attributes = TCS_STATE_ATTRIBUTES

        self._supported_features = SUPPORT_OPERATION_MODE | SUPPORT_AWAY_MODE
        self._operation_list = list(HA_STATE_TO_TCS)

    @property
    def hvac_mode(self):
        """Return the current operating mode of the evohome Controller."""
        return TCS_STATE_TO_HA.get(self._evo_device.systemModeStatus['mode'])

    @property
    def current_temperature(self):
        """Return the average current temperature of the Heating/DHW zones.

        Although evohome Controllers do not have a target temp, one is
        expected by the HA schema.
        """
        temps = [z.temperatureStatus['temperature'] for z in
                 self._evo_device._zones if z.temperatureStatus['isAvailable']]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def target_temperature(self):
        """Return the average target temperature of the Heating/DHW zones.

        Although evohome Controllers do not have a target temp, one is
        expected by the HA schema.
        """
        temps = [z.setpointStatus['targetHeatTemperature']
                 for z in self._evo_device._zones]
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def is_away_mode_on(self) -> bool:
        """Return True if away mode is on."""
        return self._evo_device.systemModeStatus['mode'] == EVO_AWAY

    @property
    def is_on(self) -> bool:
        """Return True if the evohome Controller is on."""
        return self._evo_device.systemModeStatus['mode'] != EVO_HEATOFF

    @property
    def min_temp(self):
        """Return the minimum target temperature of a evohome Controller.

        Although evohome Controllers do not have a minimum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        return 5

    @property
    def max_temp(self):
        """Return the maximum target temperature of a evohome Controller.

        Although evohome Controllers do not have a maximum target temp, one is
        expected by the HA schema; the default for an evohome HR92 is used.
        """
        return 35

    def _set_operation_mode(self, operation_mode):
        try:
            self._evo_device._set_status(operation_mode)  # noqa: E501; pylint: disable=protected-access
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode for the TCS.

        Currently limited to 'Auto', 'AutoWithEco' & 'HeatingOff'. If 'Away'
        mode is needed, it can be enabled via turn_away_mode_on method.
        """
        self._set_operation_mode(HA_STATE_TO_TCS.get(hvac_mode))

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

    async def async_update(self):
        """Process the evohome Controller's state data."""
        _LOGGER.warn("async_update(TCS=%s)", self._id)
        # _LOGGER.warn("dir(self._evo_device) = %s", dir(self._evo_device))
        # self._status = self._status
        self._available = True
