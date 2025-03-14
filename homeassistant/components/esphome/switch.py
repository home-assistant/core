"""Support for ESPHome switches."""

from __future__ import annotations

from functools import partial
from typing import Any

from aioesphomeapi import EntityInfo, SwitchInfo, SwitchState

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import callback
from homeassistant.util.enum import try_parse_enum

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)


class EsphomeSwitch(EsphomeEntity[SwitchInfo, SwitchState], SwitchEntity):
    """A switch implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        self._attr_assumed_state = static_info.assumed_state
        self._attr_device_class = try_parse_enum(
            SwitchDeviceClass, static_info.device_class
        )

    @property
    @esphome_state_property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self._state.state

    @convert_api_error_ha_error
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._client.switch_command(self._key, True)

    @convert_api_error_ha_error
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._client.switch_command(self._key, False)


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=SwitchInfo,
    entity_type=EsphomeSwitch,
    state_type=SwitchState,
)
