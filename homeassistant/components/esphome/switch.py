"""Support for ESPHome switches."""
from __future__ import annotations

from aioesphomeapi import SwitchInfo, SwitchState

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import EsphomeEntity, esphome_state_property, platform_async_setup_entry


async def async_setup_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
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


class EsphomeSwitch(EsphomeEntity, SwitchEntity):
    """A switch implementation for ESPHome."""

    @property
    def _static_info(self) -> SwitchInfo:
        return super()._static_info

    @property
    def _state(self) -> SwitchState | None:
        return super()._state

    @property
    def icon(self) -> str:
        """Return the icon."""
        return self._static_info.icon

    @property
    def assumed_state(self) -> bool:
        """Return true if we do optimistic updates."""
        return self._static_info.assumed_state

    # https://github.com/PyCQA/pylint/issues/3150 for @esphome_state_property
    # pylint: disable=invalid-overridden-method
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._state.state

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the entity on."""
        await self._client.switch_command(self._static_info.key, True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the entity off."""
        await self._client.switch_command(self._static_info.key, False)
