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
    EvoDevice,
    CONF_LOCATION_IDX)
from .const import (
    DATA_EVOHOME,
    EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER,
    GWS, TCS)

_LOGGER = logging.getLogger(__name__)

# For the DHW Controller
EVO_STATE_TO_HA = {'On': STATE_ON, 'Off': STATE_OFF}
HA_STATE_TO_EVO = {v: k for k, v in EVO_STATE_TO_HA.items()}

HA_OPMODE_TO_EVO = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the DHW controller."""
    _LOGGER.warn("setup_platform(HEATER): started")                              # TODO: delete me

    evo_data = hass.data[DATA_EVOHOME]

    client = evo_data['client']
    loc_idx = evo_data['params'][CONF_LOCATION_IDX]

    # evohomeclient has exposed no means of accessing non-default location
    # (i.e. loc_idx > 0) other than using a protected member, such as below
    evo_tcs = client.locations[loc_idx]._gateways[0]._control_systems[0]  # noqa: E501; pylint: disable=protected-access

    _LOGGER.debug(
        "Found DHW device, id: %s [%s]",
        evo_tcs.hotwater.zoneId, evo_tcs.hotwater.zone_type)

    dhw = EvoDHW(evo_data, client, evo_tcs.hotwater)

    async_add_entities([dhw], update_before_add=False)


class EvoDHW(EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_data, client, evo_dhw_ref):
        """Initialize the evohome DHW controller."""
        super().__init__(evo_data, client, evo_dhw_ref)

        self._id = evo_dhw_ref.dhwId
        self._name = "DHW controller"
        self._icon = "mdi:oil-temperature"

        self._config = evo_data['config'][GWS][0][TCS][0]['dhw']

        self._supported_features = SUPPORT_OPERATION_MODE
        self._operation_list = list(HA_OPMODE_TO_EVO)

    async def async_update(self):
        """Process the evohome Zone's state data."""
        _LOGGER.warn("async_update(DHW=%s)", self._id)
        self._status = self.hass.data[DATA_EVOHOME]['status']['dhw']
        self._available = self._status['temperatureStatus']['isAvailable']


# These properties, methods are from the WaterHeater class
    @property
    def current_operation(self) -> str:
        """Return the current operating mode (On, or Off)."""
        return EVO_STATE_TO_HA[self._status['stateStatus']['state']]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._status['temperatureStatus']['temperature']

    def set_operation_mode(self, operation_mode):
        """Set new operation mode for a DHW controller."""
        op_mode = HA_OPMODE_TO_EVO[operation_mode]

        if op_mode == EVO_FOLLOW:
            state = ''
        else:
            state = HA_STATE_TO_EVO[STATE_OFF]

        if op_mode == EVO_TEMPOVER:
            until = datetime.now() + timedelta(hours=1)
            until = until.strftime('%Y-%m-%dT%H:%M:%SZ')
        else:
            until = None

        data = {'Mode': op_mode, 'State': state, 'UntilTime': until}

        try:
            self._evo_device._set_dhw(data)  # pylint: disable=protected-access
        except requests.exceptions.HTTPError as err:
            if not self._handle_exception(err):
                raise
