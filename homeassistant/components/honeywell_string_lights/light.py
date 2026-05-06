"""Light platform for Honeywell String Lights."""

from __future__ import annotations

from typing import Any

from rf_protocols import get_codes

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .entity import HoneywellStringLightsEntity

PARALLEL_UPDATES = 1

COMMANDS = get_codes("honeywell/string_lights")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Honeywell String Lights light platform."""
    async_add_entities([HoneywellStringLight(config_entry)])


class HoneywellStringLight(HoneywellStringLightsEntity, LightEntity, RestoreEntity):
    """Representation of a Honeywell String Lights set controlled via RF."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_name = None
    _attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Restore last known state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_send_command("turn_on")
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_command("turn_off")
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_send_command(self, name: str) -> None:
        """Load the named command and send it via the configured transmitter."""
        command = await COMMANDS.async_load_command(name)
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
