"""Platform to control a Zehnder ComfoAir Q350/450/600 ventilation unit."""
from __future__ import annotations

import logging
import math
from typing import Any

from pycomfoconnect import (
    CMD_FAN_MODE_AWAY,
    CMD_FAN_MODE_HIGH,
    CMD_FAN_MODE_LOW,
    CMD_FAN_MODE_MEDIUM,
    CMD_MODE_AUTO,
    CMD_MODE_MANUAL,
    SENSOR_FAN_SPEED_MODE,
    SENSOR_OPERATING_MODE_BIS,
)

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import DOMAIN, SIGNAL_COMFOCONNECT_UPDATE_RECEIVED, ComfoConnectBridge

_LOGGER = logging.getLogger(__name__)

CMD_MAPPING = {
    0: CMD_FAN_MODE_AWAY,
    1: CMD_FAN_MODE_LOW,
    2: CMD_FAN_MODE_MEDIUM,
    3: CMD_FAN_MODE_HIGH,
}

SPEED_RANGE = (1, 3)  # away is not included in speeds and instead mapped to off

PRESET_MODE_AUTO = "auto"
PRESET_MODES = [PRESET_MODE_AUTO]


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the ComfoConnect fan platform."""
    ccb = hass.data[DOMAIN]

    add_entities([ComfoConnectFan(ccb)], True)


class ComfoConnectFan(FanEntity):
    """Representation of the ComfoConnect fan platform."""

    _attr_icon = "mdi:air-conditioner"
    _attr_should_poll = False
    _attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
    _attr_preset_modes = PRESET_MODES
    current_speed: float | None = None

    def __init__(self, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect fan."""
        self._ccb = ccb
        self._attr_name = ccb.name
        self._attr_unique_id = ccb.unique_id
        self._attr_preset_mode = None

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        _LOGGER.debug("Registering for fan speed")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_FAN_SPEED_MODE),
                self._handle_speed_update,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_OPERATING_MODE_BIS),
                self._handle_mode_update,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_FAN_SPEED_MODE
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_OPERATING_MODE_BIS
        )

    def _handle_speed_update(self, value: float) -> None:
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for fan speed (%d): %s", SENSOR_FAN_SPEED_MODE, value
        )
        self.current_speed = value
        self.schedule_update_ha_state()

    def _handle_mode_update(self, value: int) -> None:
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for operating mode (%d): %s",
            SENSOR_OPERATING_MODE_BIS,
            value,
        )
        self._attr_preset_mode = PRESET_MODE_AUTO if value == -1 else None
        self.schedule_update_ha_state()

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.current_speed is None:
            return None
        return ranged_value_to_percentage(SPEED_RANGE, self.current_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return

        if percentage is None:
            self.set_percentage(1)  # Set fan speed to low
        else:
            self.set_percentage(percentage)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan (to away)."""
        self.set_percentage(0)

    def set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        _LOGGER.debug("Changing fan speed percentage to %s", percentage)

        if percentage == 0:
            cmd = CMD_FAN_MODE_AWAY
        else:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            cmd = CMD_MAPPING[speed]

        self._ccb.comfoconnect.cmd_rmi_request(cmd)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if not self.preset_modes or preset_mode not in self.preset_modes:
            raise ValueError(f"Invalid preset mode: {preset_mode}")

        _LOGGER.debug("Changing preset mode to %s", preset_mode)
        if preset_mode == PRESET_MODE_AUTO:
            # force set it to manual first
            self._ccb.comfoconnect.cmd_rmi_request(CMD_MODE_MANUAL)
            # now set it to auto so any previous percentage set gets undone
            self._ccb.comfoconnect.cmd_rmi_request(CMD_MODE_AUTO)
