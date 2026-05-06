"""Light platform for the Novy Cooker Hood."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .commands import COMMAND_LIGHT, get_codes_for_code
from .const import CONF_CODE
from .entity import NovyCookerHoodEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Novy Cooker Hood light platform."""
    async_add_entities([NovyCookerHoodLight(config_entry)])


class NovyCookerHoodLight(NovyCookerHoodEntity, LightEntity, RestoreEntity):
    """Novy cooker hood light toggled via a single RF press."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the light."""
        super().__init__(entry)
        self._codes = get_codes_for_code(entry.data[CONF_CODE])
        self._attr_unique_id = entry.entry_id

    async def async_added_to_hass(self) -> None:
        """Restore the last known on/off state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on by sending the toggle command."""
        await self._async_send_command(COMMAND_LIGHT)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off by sending the toggle command."""
        await self._async_send_command(COMMAND_LIGHT)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_send_command(self, name: str) -> None:
        """Load the named command and send it via the configured transmitter."""
        command = await self._codes.async_load_command(name)
        await async_send_command(
            self.hass, self._transmitter, command, context=self._context
        )
