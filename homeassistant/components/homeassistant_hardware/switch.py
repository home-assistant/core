"""Home Assistant Hardware base beta firmware switch entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import FirmwareUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class BaseBetaFirmwareSwitch(SwitchEntity, RestoreEntity):
    """Base switch to enable beta firmware updates."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "beta_firmware"

    def __init__(
        self,
        coordinator: FirmwareUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the beta firmware switch."""
        self._coordinator = coordinator
        self._config_entry = config_entry

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()

        # Restore the last state
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        else:
            self._attr_is_on = False

        # Apply the restored state to the coordinator
        await self._update_coordinator_prerelease()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on beta firmware updates."""
        self._attr_is_on = True
        self.async_write_ha_state()
        await self._update_coordinator_prerelease()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off beta firmware updates."""
        self._attr_is_on = False
        self.async_write_ha_state()
        await self._update_coordinator_prerelease()

    async def _update_coordinator_prerelease(self) -> None:
        """Update the coordinator with the current prerelease setting."""
        self._coordinator.client.update_prerelease(bool(self._attr_is_on))
        await self._coordinator.async_refresh()
