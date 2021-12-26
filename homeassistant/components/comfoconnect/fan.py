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
    SENSOR_FAN_SPEED_MODE,
)

from homeassistant.components.fan import SUPPORT_SET_SPEED, FanEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ComfoConnect fan platform."""
    ccb = hass.data[DOMAIN]

    add_entities([ComfoConnectFan(ccb)], True)


class ComfoConnectFan(FanEntity):
    """Representation of the ComfoConnect fan platform."""

    current_speed = None

    def __init__(self, ccb: ComfoConnectBridge) -> None:
        """Initialize the ComfoConnect fan."""
        self._ccb = ccb

    async def async_added_to_hass(self) -> None:
        """Register for sensor updates."""
        _LOGGER.debug("Registering for fan speed")
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_COMFOCONNECT_UPDATE_RECEIVED.format(SENSOR_FAN_SPEED_MODE),
                self._handle_update,
            )
        )
        await self.hass.async_add_executor_job(
            self._ccb.comfoconnect.register_sensor, SENSOR_FAN_SPEED_MODE
        )

    def _handle_update(self, value):
        """Handle update callbacks."""
        _LOGGER.debug(
            "Handle update for fan speed (%d): %s", SENSOR_FAN_SPEED_MODE, value
        )
        self.current_speed = value
        self.schedule_update_ha_state()

    @property
    def should_poll(self) -> bool:
        """Do not poll."""
        return False

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return self._ccb.unique_id

    @property
    def name(self):
        """Return the name of the fan."""
        return self._ccb.name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:air-conditioner"

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

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
        speed: str | None = None,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
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
