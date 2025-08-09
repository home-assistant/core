"""Switch platform for Linea Research integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LineaResearchConfigEntry
from .entity import LineaResearchEntity
from .tipi_client import TIPIConnectionError, TIPIProtocolError

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LineaResearchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Linea Research switch from a config entry."""
    coordinator = config_entry.runtime_data
    
    async_add_entities([LineaResearchPowerSwitch(coordinator)])


class LineaResearchPowerSwitch(LineaResearchEntity, SwitchEntity):
    """Representation of a Linea Research amplifier power switch."""

    def __init__(self, coordinator: LineaResearchConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, "power")
        self._attr_name = "Power"
        self._attr_icon = "mdi:amplifier"

    @property
    def is_on(self) -> bool:
        """Return true if the amplifier is on."""
        return self.coordinator.data.get("power", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the amplifier on."""
        try:
            await self.coordinator.client.set_power_on()
            await self.coordinator.async_request_refresh()
        except (TIPIConnectionError, TIPIProtocolError) as err:
            _LOGGER.error("Failed to turn on amplifier: %s", err)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the amplifier off."""
        try:
            await self.coordinator.client.set_power_off()
            await self.coordinator.async_request_refresh()
        except (TIPIConnectionError, TIPIProtocolError) as err:
            _LOGGER.error("Failed to turn off amplifier: %s", err)
            raise