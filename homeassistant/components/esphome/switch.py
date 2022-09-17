"""Support for ESPHome switches."""
from __future__ import annotations

from typing import Any

from aioesphomeapi import SwitchInfo, SwitchState

from homeassistant.components.switch import DEVICE_CLASSES, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome switches based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        component_key="switch",
        info_type=SwitchInfo,
        entity_type=EsphomeSwitch,
        state_type=SwitchState,
    )


class EsphomeSwitch(EsphomeEntity[SwitchInfo, SwitchState], SwitchEntity):
    """A switch implementation for ESPHome."""

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._static_info.assumed_state

    @property  # type: ignore[misc]
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._state.state

    @property
    def device_class(self) -> str | None:
        """Return the class of this device."""
        if self._static_info.device_class not in DEVICE_CLASSES:
            return None
        return self._static_info.device_class

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        await self._client.switch_command(self._static_info.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._client.switch_command(self._static_info.key, False)
