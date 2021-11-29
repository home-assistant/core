"""Support for ESPHome buttons."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import ButtonInfo
from aioesphomeapi.model import EntityState

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome buttons based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="button",
        info_type=ButtonInfo,
        entity_type=EsphomeButton,
        state_type=EntityState,
    )


class EsphomeButton(EsphomeEntity[ButtonInfo, EntityState], ButtonEntity):
    """A button implementation for ESPHome."""

    @callback
    def _on_device_update(self) -> None:
        """Update the entity state when device info has changed."""
        # This override the EsphomeEntity method as the button entity
        # never gets a state update.
        self._on_state_update()

    async def async_press(self, **kwargs: Any) -> None:
        """Press the button."""
        await self._client.button_command(self._static_info.key)
