"""Platform to control a Renson ventilation unit."""
from __future__ import annotations

import logging
import math
from typing import Any

from renson_endura_delta.field_enum import CURRENT_LEVEL_FIELD, DataType
from renson_endura_delta.renson import Level, RensonVentilation

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import RensonCoordinator
from .const import DOMAIN
from .entity import RensonEntity

_LOGGER = logging.getLogger(__name__)

CMD_MAPPING = {
    0: Level.HOLIDAY,
    1: Level.LEVEL1,
    2: Level.LEVEL2,
    3: Level.LEVEL3,
    4: Level.LEVEL4,
}

SPEED_MAPPING = {
    Level.OFF.value: 0,
    Level.HOLIDAY.value: 0,
    Level.LEVEL1.value: 1,
    Level.LEVEL2.value: 2,
    Level.LEVEL3.value: 3,
    Level.LEVEL4.value: 4,
}


SPEED_RANGE: tuple[float, float] = (1, 4)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renson fan platform."""

    api: RensonVentilation = hass.data[DOMAIN][config_entry.entry_id].api
    coordinator: RensonCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ].coordinator

    async_add_entities([RensonFan(api, coordinator)])


class RensonFan(RensonEntity, FanEntity):
    """Representation of the Renson fan platform."""

    _attr_icon = "mdi:air-conditioner"
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = FanEntityFeature.SET_SPEED

    def __init__(self, api: RensonVentilation, coordinator: RensonCoordinator) -> None:
        """Initialize the Renson fan."""
        super().__init__("fan", api, coordinator)
        self._attr_speed_count = int_states_in_range(SPEED_RANGE)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        level = self.api.parse_value(
            self.api.get_field_value(self.coordinator.data, CURRENT_LEVEL_FIELD.name),
            DataType.LEVEL,
        )

        self._attr_percentage = ranged_value_to_percentage(
            SPEED_RANGE, SPEED_MAPPING[level]
        )

        super()._handle_coordinator_update()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is None:
            percentage = 1

        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan (to away)."""
        await self.async_set_percentage(0)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed percentage."""
        _LOGGER.debug("Changing fan speed percentage to %s", percentage)

        if percentage == 0:
            cmd = Level.HOLIDAY
        else:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
            cmd = CMD_MAPPING[speed]

        await self.hass.async_add_executor_job(self.api.set_manual_level, cmd)
