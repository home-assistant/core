"""Support for WaterHeater devices of (EMEA/EU) Honeywell TCC systems."""
import logging
from typing import List

from homeassistant.components.water_heater import (
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE,
    WaterHeaterDevice,
)
from homeassistant.const import PRECISION_WHOLE, STATE_OFF, STATE_ON
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util.dt import parse_datetime

from . import EvoChild
from .const import DOMAIN, EVO_STRFTIME, EVO_FOLLOW, EVO_TEMPOVER, EVO_PERMOVER

_LOGGER = logging.getLogger(__name__)

STATE_AUTO = "auto"

HA_STATE_TO_EVO = {STATE_AUTO: "", STATE_ON: "On", STATE_OFF: "Off"}
EVO_STATE_TO_HA = {v: k for k, v in HA_STATE_TO_EVO.items()}

STATE_ATTRS_DHW = ["dhwId", "activeFaults", "stateStatus", "temperatureStatus"]


async def async_setup_platform(
    hass: HomeAssistantType, config: ConfigType, async_add_entities, discovery_info=None
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


class EvoDHW(EvoChild, WaterHeaterDevice):
    """Base for a Honeywell evohome DHW controller (aka boiler)."""

    def __init__(self, evo_broker, evo_device) -> None:
        """Initialize the evohome DHW controller."""
        super().__init__(evo_broker, evo_device)

        self._name = "DHW controller"
        self._icon = "mdi:thermometer-lines"

        self._precision = PRECISION_WHOLE
        self._supported_features = SUPPORT_AWAY_MODE | SUPPORT_OPERATION_MODE

    @property
    def state(self):
        """Return the current state."""
        return EVO_STATE_TO_HA[self._evo_device.stateStatus["state"]]

    @property
    def current_operation(self) -> str:
        """Return the current operating mode (On, or Off)."""
        return EVO_STATE_TO_HA[self._evo_device.stateStatus["state"]]

    @property
    def operation_list(self) -> List[str]:
        """Return the list of available operations."""
        return [STATE_AUTO, STATE_ON, STATE_OFF]

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        is_off = EVO_STATE_TO_HA[self._evo_device.stateStatus["state"]] == STATE_OFF
        is_permanent = self._evo_device.stateStatus["mode"] == EVO_PERMOVER
        return is_off and is_permanent

    async def _set_dhw_state(self, op_mode, state, until=None) -> None:
        data = {"Mode": op_mode, "State": state, "UntilTime": until}
        await self._call_client_api(
            # pylint: disable=protected-access
            self._evo_device._set_dhw(data)
        )

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new operation mode for a DHW controller."""
        state = HA_STATE_TO_EVO[operation_mode]

        if operation_mode == STATE_AUTO:
            op_mode = EVO_FOLLOW
            until = None
        else:  # STATE_ON, STATE_OFF
            op_mode = EVO_TEMPOVER
            await self._update_schedule()
            until = parse_datetime(str(self.setpoints.get("next_sp_from")))

            until = until.strftime(EVO_STRFTIME) if until else None

        await self._set_dhw_state(op_mode, state, until)

    async def async_turn_away_mode_on(self):
        """Turn away mode on."""
        await self._set_dhw_state(EVO_PERMOVER, HA_STATE_TO_EVO[STATE_OFF])

    async def async_turn_away_mode_off(self):
        """Turn away mode off."""
        await self._set_dhw_state(EVO_FOLLOW, HA_STATE_TO_EVO[STATE_AUTO])

    async def async_update(self) -> None:
        """Get the latest state data for the DHW controller."""
        await super().async_update()

        for attr in STATE_ATTRS_DHW:
            self._device_state_attrs[attr] = getattr(self._evo_device, attr)
