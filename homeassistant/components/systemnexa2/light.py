"""Light entity for the SystemNexa2 integration."""

import logging
from typing import Any

import sn2
import sn2.device

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import SystemNexa2Entity
from .helpers import SystemNexa2ConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SystemNexa2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lights based on a config entry."""
    if (
        entry.runtime_data.device.info_data is None
        or not entry.runtime_data.device.info_data.dimmable
    ):
        return
    light = SN2Light(
        device=entry.runtime_data.device,
        device_info=entry.runtime_data.device_info,
        entry_id=entry.entry_id,
    )
    entry.runtime_data.main_entry = light
    entry.runtime_data.config_entries.append(light)
    async_add_entities([light])


class SN2Light(SystemNexa2Entity, LightEntity):
    """Representation of a Light."""

    def __init__(
        self, device: sn2.device.Device, device_info: DeviceInfo, entry_id: str
    ) -> None:
        """Initialize the light."""
        super().__init__(
            device,
            entry_id=entry_id,
            unique_entity_id="light1",
            name="Light",
            device_info=device_info,
        )

        self._attr_brightness = 255  # Scale from 0-255 for HA
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_available = True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # Default value -1 which is toggle
        value = -1
        # Check if we're setting brightness
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            # Convert HomeAssistant brightness (0-255) to device brightness (0-1.00)
            value = round(brightness / 255, 2)

            await self._device.set_brightness(value)
        else:
            await self._device.turn_on()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        """Turn off the light."""
        await self._device.turn_off()

    async def async_toggle(self, **_kwargs: Any) -> None:
        """Toggle the light."""
        await self._device.toggle()

    @callback
    def handle_state_update(self, state: Any) -> None:
        """Handle state updates from the device."""
        # If it's a direct boolean state
        if isinstance(state, bool):
            self._attr_is_on = state
            if state:
                self._attr_brightness = 255  # Full brightness when turned on
            self.async_write_ha_state()
            return

        # If it's a number value (0-1) for direct brightness control
        if isinstance(state, (int, float)):
            brightness_value = float(state)
            if brightness_value == 0:
                self._attr_is_on = False
            else:
                self._attr_is_on = True
                # Convert device brightness (0-1) to HomeAssistant brightness (0-255)
            self._attr_brightness = min(255, max(0, round(brightness_value * 255)))

            self.async_write_ha_state()

    @callback
    def set_available(self, *, available: bool) -> None:
        """Set availability of the entity."""
        if self._attr_available != available:
            self._attr_available = available
            _LOGGER.debug("Light %s availability set to %s", self._attr_name, available)
            self.async_write_ha_state()
