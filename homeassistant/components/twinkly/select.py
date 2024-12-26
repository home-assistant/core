"""The Twinkly select component."""

from __future__ import annotations

import logging

from ttls.client import TWINKLY_MODES

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TwinklyConfigEntry, TwinklyCoordinator
from .const import DEV_MODEL, DEV_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwinklyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setups a mode select from a config entry."""
    entity = TwinklyModeSelect(config_entry.runtime_data)
    async_add_entities([entity], update_before_add=True)


class TwinklyModeSelect(CoordinatorEntity[TwinklyCoordinator], SelectEntity):
    """Twinkly Mode Selection."""

    _attr_has_entity_name = True
    _attr_name = "Mode"
    _attr_options = TWINKLY_MODES

    def __init__(self, coordinator: TwinklyCoordinator) -> None:
        """Initialize TwinklyModeSelect."""
        super().__init__(coordinator)
        device_info = coordinator.data.device_info
        mac = device_info["mac"]

        self._attr_unique_id = f"{mac}_mode"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            connections={(CONNECTION_NETWORK_MAC, mac)},
            manufacturer="LEDWORKS",
            model=device_info[DEV_MODEL],
            name=device_info[DEV_NAME],
            sw_version=coordinator.software_version,
        )
        self.client = coordinator.client

    @property
    def current_option(self) -> str | None:
        """Return current mode."""
        return self.coordinator.data.current_mode

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.client.set_mode(option)
        await self.coordinator.async_refresh()
