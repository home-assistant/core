"""The Twinkly select component."""

from __future__ import annotations

import logging

from ttls.client import TWINKLY_MODES

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TwinklyConfigEntry, TwinklyCoordinator
from .entity import TwinklyEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwinklyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a mode select from a config entry."""
    entity = TwinklyModeSelect(config_entry.runtime_data)
    async_add_entities([entity], update_before_add=True)


class TwinklyModeSelect(TwinklyEntity, SelectEntity):
    """Twinkly Mode Selection."""

    _attr_name = "Mode"
    _attr_options = TWINKLY_MODES

    def __init__(self, coordinator: TwinklyCoordinator) -> None:
        """Initialize TwinklyModeSelect."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.data.device_info['mac']}_mode"
        self.client = coordinator.client

    @property
    def current_option(self) -> str | None:
        """Return current mode."""
        return self.coordinator.data.current_mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.client.set_mode(option)
        await self.coordinator.async_refresh()
