"""Platform to control a Salda Smarty XP/XV ventilation unit."""

from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from . import SmartyConfigEntry
from .coordinator import SmartyCoordinator
from .entity import SmartyEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_ON_PERCENTAGE = 66
SPEED_RANGE = (1, 3)  # off is not included


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Fan Platform."""

    coordinator = entry.runtime_data

    async_add_entities([SmartyFan(coordinator)])


class SmartyFan(SmartyEntity, FanEntity):
    """Representation of a Smarty Fan."""

    _attr_name = None
    _attr_translation_key = "fan"
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: SmartyCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._smarty_fan_speed = 0
        self._smarty = coordinator.client
        self._attr_unique_id = coordinator.config_entry.entry_id

    @property
    def is_on(self) -> bool:
        """Return state of the fan."""
        return bool(self._smarty_fan_speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(SPEED_RANGE)

    @property
    def percentage(self) -> int:
        """Return speed percentage of the fan."""
        if self._smarty_fan_speed == 0:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, self._smarty_fan_speed)

    def set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        _LOGGER.debug("Set the fan percentage to %s", percentage)
        if percentage == 0:
            self.turn_off()
            return

        fan_speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        if not self._smarty.set_fan_speed(fan_speed):
            raise HomeAssistantError(
                f"Failed to set the fan speed percentage to {percentage}"
            )

        self._smarty_fan_speed = fan_speed
        self.schedule_update_ha_state()

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Turning on fan. percentage is %s", percentage)
        self.set_percentage(percentage or DEFAULT_ON_PERCENTAGE)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        _LOGGER.debug("Turning off fan")
        if not self._smarty.turn_off():
            raise HomeAssistantError("Failed to turn off the fan")

        self._smarty_fan_speed = 0
        self.schedule_update_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Call update method."""
        self._smarty_fan_speed = self._smarty.fan_speed
        super()._handle_coordinator_update()
