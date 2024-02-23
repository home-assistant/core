"""Support for Balboa Spa pumps."""
from __future__ import annotations

from typing import Any
import math

from pybalboa import SpaClient
from pybalboa.enums import OffOnState

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import DOMAIN
from .entity import BalboaToggleEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's pumps."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    entities = [BalboaPumpFanEntity(control) for control in spa.pumps]
    async_add_entities(entities)


PUMP_ICON_ON = "mdi:pump"
PUMP_ICON_OFF = "mdi:pump-off"


class BalboaPumpFanEntity(BalboaToggleEntity, FanEntity):
    """Representation of a Balboa Spa pump fan entity."""

    _attr_supported_features = FanEntityFeature.SET_SPEED
    _attr_translation_key = "pump"

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any
    ) -> None:
        if percentage is None:
            percentage = 100
        await self.async_set_percentage(percentage)

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage > 0:
            state = math.ceil(percentage_to_ranged_value((1, self.speed_count), percentage))
        else:
            state = OffOnState.OFF
        await self._control.set_state(state)

    @property
    def percentage(self) -> int | None:
        if self._control.state == OffOnState.OFF:
            return 0
        return ranged_value_to_percentage((1, self.speed_count), self._control.state)

    @property
    def icon(self) -> str | None:
        return PUMP_ICON_ON if self.is_on else PUMP_ICON_OFF

    @property
    def speed_count(self) -> int:
        return int(max(self._control.options))
