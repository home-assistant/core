"""Light platform for Honeywell String Lights."""

from __future__ import annotations

from typing import Any

from rf_protocols import (
    HoneywellStringLightsTurnOff,
    HoneywellStringLightsTurnOn,
    RadioFrequencyCommand,
)

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.components.radio_frequency import async_send_command
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_TRANSMITTER, DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Honeywell String Lights light platform."""
    async_add_entities([HoneywellStringLight(config_entry)])


class HoneywellStringLight(LightEntity, RestoreEntity):
    """Representation of a Honeywell String Lights set controlled via RF."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the light."""
        self._transmitter = config_entry.data[CONF_TRANSMITTER]
        self._attr_unique_id = config_entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            manufacturer="Honeywell",
            model="String Lights",
            name=config_entry.title,
        )
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Restore last known state."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_send_command(HoneywellStringLightsTurnOn())
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_send_command(HoneywellStringLightsTurnOff())
        self._attr_is_on = False
        self.async_write_ha_state()

    async def _async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Send an RF command using the configured transmitter."""
        await async_send_command(self.hass, self._transmitter, command)
