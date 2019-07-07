"""Support for Climate devices of (EMEA/EU-based) Honeywell TCC systems."""
from datetime import datetime
import logging
from typing import Optional, List

import requests.exceptions
import evohomeclient2

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT, HVAC_MODE_AUTO, HVAC_MODE_OFF,
    PRESET_AWAY, PRESET_ECO, PRESET_HOME,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE)

from . import CONF_LOCATION_IDX, _handle_exception, EvoDevice
from .const import (
    DOMAIN, EVO_STRFTIME,
    EVO_RESET, EVO_AUTO, EVO_AUTOECO, EVO_AWAY, EVO_DAYOFF, EVO_CUSTOM,
    EVO_HEATOFF, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER)

_LOGGER = logging.getLogger(__name__)

PRESET_RESET = 'Reset'  # reset all child zones to EVO_FOLLOW
PRESET_CUSTOM = 'Custom'

HA_HVAC_TO_TCS = {
    HVAC_MODE_OFF: EVO_HEATOFF,
    HVAC_MODE_HEAT: EVO_AUTO,
}
HA_PRESET_TO_TCS = {
    PRESET_AWAY: EVO_AWAY,
    PRESET_CUSTOM: EVO_CUSTOM,
    PRESET_ECO: EVO_AUTOECO,
    PRESET_HOME: EVO_DAYOFF,
    PRESET_RESET: EVO_RESET,
}
TCS_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_TCS.items()}

HA_PRESET_TO_EVO = {
    'temporary': EVO_TEMPOVER,
    'permanent': EVO_PERMOVER,
}
EVO_PRESET_TO_HA = {v: k for k, v in HA_PRESET_TO_EVO.items()}


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None) -> None:
    """Create the evohome Controller, and its Zones, if any."""
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


class EvoClimateDevice(EvoDevice, ClimateDevice):
    """Base for a Honeywell evohome Climate device."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome Climate device."""
        super().__init__(evo_broker, evo_device)

        self._hvac_modes = self._preset_modes = None

    @property
    def hvac_modes(self) -> List[str]:
        """Return the list of available hvac operation modes."""
        return self._hvac_modes

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes."""
        return self._preset_modes


class EvoZone(EvoClimateDevice):
    """Base for a Honeywell evohome Zone."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome Zone."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.zoneId
        self._name = evo_device.name
        self._icon = 'mdi:radiator'

        self._precision = \
            self._evo_device.setpointCapabilities['valueResolution']
        self._state_attributes = [
            'activeFaults', 'setpointStatus', 'temperatureStatus', 'setpoints']

        self._supported_features = SUPPORT_PRESET_MODE | \
            SUPPORT_TARGET_TEMPERATURE
        self._hvac_modes = [HVAC_MODE_OFF, HVAC_MODE_HEAT]
        self._preset_modes = list(HA_PRESET_TO_EVO)

        for _zone in evo_broker.config['zones']:
            if _zone['zoneId'] == self._id:
                self._config = _zone
                break

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode of the evohome Zone.

        NB: evohome Zones 'inherit' their operating mode from the controller.

        Usually, Zones are in 'FollowSchedule' mode, where their setpoints are
        a function of their schedule, and the Controller's operating_mode, e.g.
        Economy mode is their scheduled setpoint less (usually) 3C.

        However, Zones can override these setpoints, either for a specified
        period of time, 'TemporaryOverride', after which they will revert back
        to 'FollowSchedule' mode, or indefinitely, 'PermanentOverride'.
        """
        if self._evo_tcs.systemModeStatus['mode'] in [EVO_AWAY, EVO_HEATOFF]:
            return HVAC_MODE_AUTO
        is_off = self.target_temperature <= self.min_temp
        return HVAC_MODE_OFF if is_off else HVAC_MODE_HEAT

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature of the evohome Zone."""
        return (self._evo_device.temperatureStatus['temperature']
                if self._evo_device.temperatureStatus['isAvailable'] else None)

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the target temperature of the evohome Zone."""
        if self._evo_tcs.systemModeStatus['mode'] == EVO_HEATOFF:
            return self._evo_device.setpointCapabilities['minHeatSetpoint']
        return self._evo_device.setpointStatus['targetHeatTemperature']

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        if self._evo_tcs.systemModeStatus['mode'] in [EVO_AWAY, EVO_HEATOFF]:
            return None
        return EVO_PRESET_TO_HA.get(
            self._evo_device.setpointStatus['setpointMode'], 'follow')

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature of a evohome Zone.

        The default is 5, but is user-configurable within 5-35 (in Celsius).
        """
        return self._evo_device.setpointCapabilities['minHeatSetpoint']

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature of a evohome Zone.

        The default is 35, but is user-configurable within 5-35 (in Celsius).
        """
        return self._evo_device.setpointCapabilities['maxHeatSetpoint']

    def _set_temperature(self, temperature: float,
                         until: Optional[datetime] = None):
        """Set a new target temperature for the Zone.

        until == None means indefinitely (i.e. PermanentOverride)
        """
        try:
            self._evo_device.set_temperature(temperature, until)
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            _handle_exception(err)

    def set_temperature(self, **kwargs) -> None:
        """Set a new target temperature for an hour."""
        until = kwargs.get('until')
        if until:
            until = datetime.strptime(until, EVO_STRFTIME)

        self._set_temperature(kwargs['temperature'], until)

    def _set_operation_mode(self, op_mode) -> None:
        """Set the Zone to one of its native EVO_* operating modes."""
        if op_mode == EVO_FOLLOW:
            try:
                self._evo_device.cancel_temp_override()
            except (requests.exceptions.RequestException,
                    evohomeclient2.AuthenticationError) as err:
                _handle_exception(err)
            return

        self._setpoints = self.get_setpoints()
        temperature = self._evo_device.setpointStatus['targetHeatTemperature']

        if op_mode == EVO_TEMPOVER:
            until = self._setpoints['next']['from_datetime']
            until = datetime.strptime(until, EVO_STRFTIME)
        else:  # EVO_PERMOVER:
            until = None

        self._set_temperature(temperature, until=until)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set an operating mode for the Zone."""
        if hvac_mode == HVAC_MODE_OFF:
            self._set_temperature(self.min_temp, until=None)

        else:  # HVAC_MODE_HEAT
            self._set_operation_mode(EVO_FOLLOW)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set a new preset mode.

        If preset_mode is None, then revert to following the schedule.
        """
        self._set_operation_mode(HA_PRESET_TO_EVO.get(preset_mode, EVO_FOLLOW))


class EvoController(EvoClimateDevice):
    """Base for a Honeywell evohome Controller (hub).

    The Controller (aka TCS, temperature control system) is the parent of all
    the child (CH/DHW) devices.  It is also a Climate device.
    """

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome Controller (hub)."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.systemId
        self._name = evo_device.location.name
        self._icon = 'mdi:thermostat'

        self._precision = None
        self._state_attributes = [
            'activeFaults', 'systemModeStatus']

        self._supported_features = SUPPORT_PRESET_MODE
        self._hvac_modes = list(HA_HVAC_TO_TCS)
        self._preset_modes = list(HA_PRESET_TO_TCS)

        self._config = dict(evo_broker.config)
        self._config['zones'] = '...'
        if 'dhw' in self._config:
            self._config['dhw'] = '...'

    @property
    def hvac_mode(self) -> str:
        """Return the current operating mode of the evohome Controller."""
        tcs_mode = self._evo_device.systemModeStatus['mode']
        return HVAC_MODE_OFF if tcs_mode == EVO_HEATOFF else HVAC_MODE_HEAT

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the average current temperature of the heating Zones.

        Controllers do not have a current temp, but one is expected by HA.
        """
        temps = [z.temperatureStatus['temperature'] for z in
                 self._evo_device._zones if z.temperatureStatus['isAvailable']]  # noqa: E501; pylint: disable=protected-access
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def target_temperature(self) -> Optional[float]:
        """Return the average target temperature of the heating Zones.

        Controllers do not have a target temp, but one is expected by HA.
        """
        temps = [z.setpointStatus['targetHeatTemperature']
                 for z in self._evo_device._zones]                               # noqa: E501; pylint: disable=protected-access
        return round(sum(temps) / len(temps), 1) if temps else None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp."""
        return TCS_PRESET_TO_HA.get(self._evo_device.systemModeStatus['mode'])

    @property
    def min_temp(self) -> float:
        """Return the minimum target temperature  of the heating Zones.

        Controllers do not have a min target temp, but one is required by HA.
        """
        temps = [z.setpointCapabilities['minHeatSetpoint']
                 for z in self._evo_device._zones]  # noqa: E501; pylint: disable=protected-access
        return min(temps) if temps else 5

    @property
    def max_temp(self) -> float:
        """Return the maximum target temperature  of the heating Zones.

        Controllers do not have a max target temp, but one is required by HA.
        """
        temps = [z.setpointCapabilities['maxHeatSetpoint']
                 for z in self._evo_device._zones]  # noqa: E501; pylint: disable=protected-access
        return max(temps) if temps else 35

    def _set_operation_mode(self, op_mode) -> None:
        """Set the Controller to any of its native EVO_* operating modes."""
        try:
            self._evo_device._set_status(op_mode)  # noqa: E501; pylint: disable=protected-access
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            _handle_exception(err)

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set an operating mode for the Controller."""
        self._set_operation_mode(HA_HVAC_TO_TCS.get(hvac_mode))

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set a new preset mode.

        If preset_mode is None, then revert to 'Auto' mode.
        """
        self._set_operation_mode(HA_PRESET_TO_TCS.get(preset_mode, EVO_AUTO))

    def update(self) -> None:
        """Get the latest state data."""
        pass
