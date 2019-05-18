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
from .climate import (
    EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER)
from .const import (
    DATA_EVOHOME, GWS, TCS)

_LOGGER = logging.getLogger(__name__)

EVO_STATE_TO_HA = {'On': STATE_ON, 'Off': STATE_OFF}
HA_STATE_TO_EVO = {v: k for k, v in EVO_STATE_TO_HA.items()}

HA_OPMODE_TO_EVO = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}


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


class EvoDHW(EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_data, client, obj_ref):
        """Initialize the evohome DHW controller."""
        super().__init__(evo_data, client, obj_ref)

        self._id = obj_ref.dhwId
        self._name = "DHW controller"
        self._icon = "mdi:oil-temperature"

        self._config = evo_data['config'][GWS][0][TCS][0]['dhw']

        self._supported_features = SUPPORT_OPERATION_MODE
        self._operation_list = list(HA_OPMODE_TO_EVO)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

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
            self._obj._set_dhw(data)  # pylint: disable=protected-access
        except requests.exceptions.HTTPError as err:
            if not self._handle_exception(err):
                raise

    async def async_update(self):
        """Process the evohome Zone's state data."""
        self._status = self.hass.data[DATA_EVOHOME]['status']['dhw']
        self._available = self._status['temperatureStatus']['isAvailable']
