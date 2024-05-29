"""Support for Balboa Spa pumps."""

from __future__ import annotations

import math
from typing import Any, cast

from pybalboa import SpaClient, SpaControl
from pybalboa.enums import OffOnState, UnknownState

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .entity import BalboaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's pumps."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BalboaPumpFanEntity(control) for control in spa.pumps)


class BalboaPumpFanEntity(BalboaEntity, FanEntity):
    """Representation of a Balboa Spa pump fan entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_translation_key = "pump"

    def __init__(self, control: SpaControl) -> None:
        """Initialize a Balboa pump fan entity."""
        super().__init__(control.client, control.name)
        self._control = control
        self._attr_translation_placeholders = {
            "index": f"{cast(int, control.index) + 1}"
        }

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the pump off."""
        await self._control.set_state(OffOnState.OFF)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the pump on (by default on max speed)."""
        if percentage is None:
            percentage = 100
        await self.async_set_percentage(percentage)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the pump."""
        if percentage > 0:
            state = math.ceil(
                percentage_to_ranged_value((1, self.speed_count), percentage)
            )
        else:
            state = OffOnState.OFF
        await self._control.set_state(state)

    @property
    def percentage(self) -> int | None:
        """Return the speed of the pump."""
        if self._control.state == UnknownState.UNKNOWN:
            return None
        if self._control.state == OffOnState.OFF:
            return 0
        return ranged_value_to_percentage((1, self.speed_count), self._control.state)

    @property
    def is_on(self) -> bool | None:
        """Return true if the pump is running."""
        if self._control.state == UnknownState.UNKNOWN:
            return None
        return self._control.state != OffOnState.OFF

    @property
    def speed_count(self) -> int:
        """Return the number of different speed settings the pump supports."""
        return int(max(self._control.options))
