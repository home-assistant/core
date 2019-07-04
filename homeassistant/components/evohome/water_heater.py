"""Support for WaterHeater devices of (EMEA/EU) Honeywell TCC systems."""
from datetime import datetime, timedelta
import logging
from typing import Any, Awaitable, Dict, Optional, List

import requests.exceptions
import evohomeclient2

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE, WaterHeaterDevice)
from homeassistant.const import PRECISION_WHOLE, STATE_OFF, STATE_ON

from . import _handle_exception, EvoDevice
from .const import DOMAIN, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER

_LOGGER = logging.getLogger(__name__)

HA_STATE_TO_EVO = {STATE_ON: 'On', STATE_OFF: 'Off'}
EVO_STATE_TO_HA = {v: k for k, v in HA_STATE_TO_EVO.items()}

HA_OPMODE_TO_DHW = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}

DHW_STATE_ATTRIBUTES = ['activeFaults', 'stateStatus', 'temperatureStatus']


async def async_setup_platform(hass, hass_config, async_add_entities,
                               discovery_info=None):
    """Create the DHW controller."""
    broker = hass.data[DOMAIN]['broker']

    _LOGGER.debug(
        "Found DHW device, id: %s [%s]",
        broker.tcs.hotwater.zoneId, broker.tcs.hotwater.zone_type)

    evo_dhw = EvoDHW(broker, broker.tcs.hotwater)

    async_add_entities([evo_dhw], update_before_add=True)


class EvoDHW(EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome DHW controller."""
        super().__init__(evo_broker, evo_device)

        self._id = evo_device.dhwId
        self._name = "DHW controller"
        self._icon = "mdi:oil-temperature"
        self._precision = PRECISION_WHOLE

        self._config = evo_broker.config['dhw']

        self._state_attributes = DHW_STATE_ATTRIBUTES
        self._operation_list = list(HA_OPMODE_TO_DHW)
        self._supported_features = SUPPORT_OPERATION_MODE

    @property
    def current_operation(self) -> str:
        """Return the current operating mode (On, or Off)."""
        return EVO_STATE_TO_HA[self._evo_device.stateStatus['state']]

    @property
    def operation_list(self) -> List[str]:
        """Return the list of available operations."""
        return self._operation_list

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._evo_device.temperatureStatus['temperature']

    def set_operation_mode(self, operation_mode: str) -> None:
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
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            _handle_exception(err)

    async def async_update(self)  -> Awaitable[None]:
        """Process the evohome DHW controller's state data."""
        self._available = self._evo_device.temperatureStatus['isAvailable']
