"""Support for WaterHeater devices of (EMEA/EU) Honeywell evohome systems."""
from datetime import datetime, timedelta
import logging

import requests.exceptions

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice)
from homeassistant.const import (
    STATE_OFF, STATE_ON)

from . import (
    EvoDevice, EvoChildDevice,
    CONF_LOCATION_IDX,
)
from .climate import (
    EVO_FOLLOW, EVO_TEMPOVER,
    ZONE_OP_LIST,
)
from .const import (
    DATA_EVOHOME, GWS, TCS
)

DHW_STATES = {STATE_ON: 'On', STATE_OFF: 'Off'}

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the DHW controller."""
    evo_data = hass.data[DATA_EVOHOME]

    client = evo_data['client']
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]

    # evohomeclient has exposed no means of accessing non-default location
    # (i.e. loc_idx > 0) other than using a protected member, such as below
    tcs_obj_ref = client.locations[loc_idx]._gateways[0]._control_systems[0]  # noqa: E501; pylint: disable=protected-access

    _LOGGER.info(
        "setup(): Found DHW device, id: %s [%s]",
        tcs_obj_ref.hotwater.zoneId, tcs_obj_ref.hotwater.zone_type)

    dhw = EvoDHW(evo_data, client, tcs_obj_ref.hotwater)

    async_add_entities([dhw], update_before_add=False)


class EvoDHW(EvoChildDevice, EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome DHW controller."""
        super().__init__(evo_data, client, obj_ref)

        self._id = obj_ref.dhwId
        self._name = "DHW controller"
        self._icon = "oil-temperature"

        self._config = evo_data['config'][GWS][0][TCS][0]['dhw']

        self._operation_list = ZONE_OP_LIST
        self._supported_features = SUPPORT_OPERATION_MODE

    @property
    def target_temperature(self):
        """Return the target temperature.

        Note that the API does not expose the target temperature, so a
        configured value is used here.
        """
        # A workaround, since water_heaters don't have a current temperature!
        # temp = self._params[CONF_DHW_TEMP]
        if self._status['temperatureStatus']['isAvailable']:
            temp = self._status['temperatureStatus']['temperature']
        else:
            temp = None

        return temp

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

        if state is None:
            state = self._status['stateStatus']['state']
        if mode is None:
            mode = EVO_TEMPOVER

        if mode != EVO_TEMPOVER:
            until = None
        else:
            if until is None:
                until = datetime.now() + timedelta(hours=1)

        if until is not None:
            until = until.strftime('%Y-%m-%dT%H:%M:%SZ')

        data = {'State': state, 'Mode': mode, 'UntilTime': until}

        try:
            self._obj._set_dhw(data)  # pylint: disable=protected-access

        except requests.exceptions.HTTPError as err:
            if not self._handle_exception(err):
                raise

    @property
    def is_on(self):
        """Return True if DHW is on (albeit regulated by thermostat)."""
        return self.state == DHW_STATES[STATE_ON]

    def turn_on(self):
        """Turn DHW on for an hour, until next setpoint, or indefinitely."""
        mode = EVO_TEMPOVER
        until = None

        self._set_dhw_state(DHW_STATES[STATE_ON], mode, until)

    def turn_off(self):
        """Turn DHW off for an hour, until next setpoint, or indefinitely."""
        mode = EVO_TEMPOVER
        until = None

        self._set_dhw_state(DHW_STATES[STATE_OFF], mode, until)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode for a DHW controller."""
        if operation_mode == EVO_FOLLOW:
            state = ''
        else:
            state = self._status['stateStatus']['state']

        if operation_mode == EVO_TEMPOVER:
            until = datetime.now() + timedelta(hours=1)
            until = until.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            until = None

        self._set_dhw_state(state, operation_mode, until)
