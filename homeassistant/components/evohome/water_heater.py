"""Support for WaterHeater devices of (EMEA/EU) Honeywell TCC systems."""
import logging
from typing import List

from homeassistant.components.water_heater import (
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice,
)
from homeassistant.const import PRECISION_WHOLE, STATE_OFF, STATE_ON
from homeassistant.util.dt import parse_datetime

from . import EvoDevice
from .const import DOMAIN, EVO_STRFTIME, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER

_LOGGER = logging.getLogger(__name__)

HA_STATE_TO_EVO = {STATE_ON: "On", STATE_OFF: "Off"}
EVO_STATE_TO_HA = {v: k for k, v in HA_STATE_TO_EVO.items()}

HA_OPMODE_TO_DHW = {STATE_ON: EVO_FOLLOW, STATE_OFF: EVO_PERMOVER}


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> None:
    """Create the DHW controller."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    _LOGGER.debug(
        "Found %s, id: %s", broker.tcs.hotwater.zone_type, broker.tcs.hotwater.zoneId
    )

    evo_dhw = EvoDHW(broker, broker.tcs.hotwater)

    async_add_entities([evo_dhw], update_before_add=True)


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
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._evo_device.temperatureStatus.get("isAvailable", False)

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

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode for a DHW controller."""
        op_mode = HA_OPMODE_TO_DHW[operation_mode]

        state = "" if op_mode == EVO_FOLLOW else HA_STATE_TO_EVO[STATE_OFF]
        until = None  # EVO_FOLLOW, EVO_PERMOVER

        if op_mode == EVO_TEMPOVER and self._schedule["DailySchedules"]:
            await self._update_schedule()
            if self._schedule["DailySchedules"]:
                until = parse_datetime(self.setpoints["next"]["from"])
                until = until.strftime(EVO_STRFTIME)

        data = {"Mode": op_mode, "State": state, "UntilTime": until}

        await self._call_client_api(
            self._evo_device._set_dhw(data)  # pylint: disable=protected-access
        )
