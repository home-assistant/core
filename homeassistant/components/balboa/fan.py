"""Support for Balboa Spa Pumps."""
from __future__ import annotations

from typing import Any

from pybalboa import SpaClient, SpaControl

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import DOMAIN
from .entity import BalboaControlEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the spa's pumps as FAN entities."""
    spa: SpaClient = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(BalboaPumpEntity(pump) for pump in spa.pumps)


class BalboaPumpEntity(BalboaControlEntity, FanEntity):
    """Balboa spa pump entity."""

    _attr_icon = "mdi:hydro-power"

    def __init__(self, pump: SpaControl) -> None:
        """Initialize the pump."""
        super().__init__(pump)
        if max(pump.options) > 1:
            self._attr_supported_features |= FanEntityFeature.SET_SPEED

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the pump, as a percentage."""
        if percentage == 0:
            state = self._control.options[0]
        else:
            state = percentage_to_ordered_list_item(
                self._control.options[1:], percentage
            )
        await self._control.set_state(state)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the pump."""
        if percentage is None:
            percentage = 1
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the pump."""
        await self.async_set_percentage(0)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the pump supports."""
        return max(self._control.options)

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if self._control.state > 0:
            return ordered_list_item_to_percentage(
                self._control.options[1:], self._control.state
            )
        return 0

    @property
    def is_on(self) -> bool:
        """Return true if the pump is on."""
        return self._control.state > 0
