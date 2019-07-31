"""Support for WaterHeater devices of (EMEA/EU) Honeywell TCC systems."""
import logging
from typing import List

import requests.exceptions
import evohomeclient2

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice,
)
from homeassistant.const import PRECISION_WHOLE, STATE_OFF, STATE_ON
from homeassistant.util.dt import parse_datetime

from . import _handle_exception, EvoDevice
from .const import DOMAIN, EVO_STRFTIME, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER

_LOGGER = logging.getLogger(__name__)

HA_STATE_TO_EVO = {STATE_ON: "On", STATE_OFF: "Off"}
EVO_STATE_TO_HA = {v: k for k, v in HA_STATE_TO_EVO.items()}

HA_OPMODE_TO_DHW = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}


def setup_platform(hass, hass_config, add_entities, discovery_info=None) -> None:
    """Create the DHW controller."""
    broker = hass.data[DOMAIN]["broker"]

    _LOGGER.debug(
        "Found %s, id: %s", broker.tcs.hotwater.zone_type, broker.tcs.hotwater.zoneId
    )

    evo_dhw = EvoDHW(broker, broker.tcs.hotwater)

    add_entities([evo_dhw], update_before_add=True)


class EvoDHW(EvoDevice, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome DHW controller."""
        super().__init__(evo_broker, evo_device)

        self._name = "DHW controller"
        self._icon = "mdi:thermometer-lines"

        self._precision = PRECISION_WHOLE
        self._state_attributes = [
            "dhwId",
            "activeFaults",
            "stateStatus",
            "temperatureStatus",
            "setpoints",
        ]

        self._supported_features = SUPPORT_OPERATION_MODE
        self._operation_list = list(HA_OPMODE_TO_DHW)

    @property
    def current_operation(self) -> str:
        """Return the current operating mode (On, or Off)."""
        return EVO_STATE_TO_HA[self._evo_device.stateStatus["state"]]

    @property
    def operation_list(self) -> List[str]:
        """Return the list of available operations."""
        return self._operation_list

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._evo_device.temperatureStatus["temperature"]

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode for a DHW controller."""
        op_mode = HA_OPMODE_TO_DHW[operation_mode]

        state = "" if op_mode == EVO_FOLLOW else HA_STATE_TO_EVO[STATE_OFF]
        until = None  # EVO_FOLLOW, EVO_PERMOVER

        if op_mode == EVO_TEMPOVER and self._schedule["DailySchedules"]:
            self._update_schedule()
            if self._schedule["DailySchedules"]:
                until = parse_datetime(self.setpoints["next"]["from"])
                until = until.strftime(EVO_STRFTIME)

        data = {"Mode": op_mode, "State": state, "UntilTime": until}

        try:
            self._evo_device._set_dhw(data)  # pylint: disable=protected-access
        except (
            requests.exceptions.RequestException,
            evohomeclient2.AuthenticationError,
        ) as err:
            _handle_exception(err)
