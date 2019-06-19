"""Support for WaterHeater devices of (EMEA/EU) Honeywell TCC systems."""
from datetime import datetime, timedelta
import logging

import requests.exceptions

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice)
from homeassistant.const import (
    PRECISION_WHOLE, STATE_OFF, STATE_ON)

from . import (EvoDevice, CONF_LOCATION_IDX)
from .const import (
    DOMAIN, GWS, TCS,
    EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER)

_LOGGER = logging.getLogger(__name__)

# For the DHW Controller
EVO_STATE_TO_HA = {'On': STATE_ON, 'Off': STATE_OFF}
HA_STATE_TO_EVO = {v: k for k, v in EVO_STATE_TO_HA.items()}

HA_OPMODE_TO_DHW = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}

DHW_STATE_ATTRIBUTES = ['activeFaults', 'stateStatus', 'temperatureStatus']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the DHW controller."""
    _LOGGER.warn("async_setup_platform(HEATER): hass_config=%s", hass_config)    # TODO: delete me

    broker = hass.data[DOMAIN]['broker']
    loc_idx = broker.params[CONF_LOCATION_IDX]

    _LOGGER.debug(
        "Found DHW device, id: %s [%s]",
        broker.tcs.hotwater.zoneId, broker.tcs.hotwater.zone_type)

    evo_dhw = EvoDHW(broker, broker.tcs.hotwater)

    async_add_entities([evo_dhw], update_before_add=True)


class EvoDHW(EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_broker, evo_device):
        """Initialize the evohome DHW controller."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.dhwId
        self._name = "DHW controller"
        self._icon = "mdi:oil-temperature"
        self._precision = PRECISION_WHOLE

        self._config = evo_broker.config['dhw']
        _LOGGER.warn("__init__(DHW): self._config = %s", self._config)           # TODO: remove

        self._precision = PRECISION_WHOLE

        self._state_attributes = DHW_STATE_ATTRIBUTES
        self._operation_list = list(HA_OPMODE_TO_DHW)
        self._supported_features = SUPPORT_OPERATION_MODE

    async def async_update(self):
        """Process the evohome DHW controller's state data."""
        _LOGGER.warn("async_update(DHW=%s)", self._id)

        # self._status = self._status['dhw']
        self._available = self._evo_device.temperatureStatus['isAvailable']


# These properties, methods are from the WaterHeater class  # TODO: remove me
    @property
    def current_operation(self) -> str:
        """Return the current operating mode (On, or Off)."""
        return EVO_STATE_TO_HA[self._evo_device.stateStatus['state']]

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._evo_device.temperatureStatus['temperature']

    def set_operation_mode(self, operation_mode):
        """Set new operation mode for a DHW controller."""
        op_mode = HA_OPMODE_TO_DHW[operation_mode]

        state = '' if op_mode == EVO_FOLLOW else HA_STATE_TO_EVO[STATE_OFF]

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
