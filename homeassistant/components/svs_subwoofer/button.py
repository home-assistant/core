"""Button platform for SVS Subwoofer."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SVSConfigEntry
from .coordinator import SVSSubwooferCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SVSConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SVS button entities."""
    coordinator = entry.runtime_data

    entities = [
        SVSReconnectButton(coordinator),
        SVSSavePresetButton(coordinator, 1),
        SVSSavePresetButton(coordinator, 2),
        SVSSavePresetButton(coordinator, 3),
    ]
    async_add_entities(entities)


class SVSReconnectButton(CoordinatorEntity[SVSSubwooferCoordinator], ButtonEntity):
    """Button to reconnect to the subwoofer."""

    _attr_has_entity_name = True
    _attr_translation_key = "reconnect"
    _attr_icon = "mdi:bluetooth-connect"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SVSSubwooferCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address}_reconnect"
        self._attr_device_info = coordinator.device_info

    async def async_press(self) -> None:
        """Handle button press - reconnect to subwoofer."""
        _LOGGER.debug("Reconnect button pressed for %s", self.coordinator.address)

        # Disconnect first if connected
        if self.coordinator.is_connected:
            await self.coordinator.async_disconnect()

        # Request a refresh which will trigger reconnection
        await self.coordinator.async_request_refresh()


class SVSSavePresetButton(CoordinatorEntity[SVSSubwooferCoordinator], ButtonEntity):
    """Button to save current settings to a preset slot."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:content-save"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: SVSSubwooferCoordinator, preset_number: int
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._preset_number = preset_number
        self._attr_unique_id = f"{coordinator.address}_save_preset_{preset_number}"
        self._attr_device_info = coordinator.device_info
        self._attr_translation_key = f"save_preset_{preset_number}"

    async def async_press(self) -> None:
        """Handle button press - save current settings to preset."""
        _LOGGER.debug(
            "Save preset %d button pressed for %s",
            self._preset_number,
            self.coordinator.address,
        )
        await self.coordinator.async_save_preset(self._preset_number)
