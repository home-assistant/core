"""Support for ESPHome buttons."""

from __future__ import annotations

from functools import partial

from aioesphomeapi import ButtonInfo, EntityInfo, EntityState

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import callback
from homeassistant.util.enum import try_parse_enum

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    platform_async_setup_entry,
)

PARALLEL_UPDATES = 0


class EsphomeButton(EsphomeEntity[ButtonInfo, EntityState], ButtonEntity):
    """A button implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        self._attr_device_class = try_parse_enum(
            ButtonDeviceClass, self._static_info.device_class
        )

    @callback
    def _on_device_update(self) -> None:
        """Call when device updates or entry data changes.

        The default behavior is only to write entity state when the
        device is unavailable when the device state changes.
        This method overrides the default behavior since buttons do
        not have a state, so we will never get a state update for a
        button. As such, we need to write the state on every device
        update to ensure the button goes available and unavailable
        as the device becomes available or unavailable.
        """
        self._on_entry_data_changed()
        self.async_write_ha_state()

    @convert_api_error_ha_error
    async def async_press(self) -> None:
        """Press the button."""
        self._client.button_command(self._key)


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=ButtonInfo,
    entity_type=EsphomeButton,
    state_type=EntityState,
)
