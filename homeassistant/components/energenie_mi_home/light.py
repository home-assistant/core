"""Light platform for Energenie Mi Home."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICE_TYPE_LIGHT_SWITCH
from .coordinator import MiHomeConfigEntry
from .entity import MiHomeEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MiHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mi Home light entities."""
    coordinator = config_entry.runtime_data

    # Filter for light switch devices
    entities = [
        MiHomeLightEntity(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.device_type == DEVICE_TYPE_LIGHT_SWITCH
    ]

    if entities:
        async_add_entities(entities)


class MiHomeLightEntity(MiHomeEntity, LightEntity):
    """Representation of a Mi Home light switch."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        device = self.coordinator.data.get(self.device_id)
        return device.is_on if device else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug("Turning on light %s", self.device_id)
        try:
            await self.coordinator.api.async_set_device_state(self.device_id, True)
            _LOGGER.debug(
                "Successfully sent turn on command for light %s", self.device_id
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception("Failed to turn on light %s", self.device_id)
            raise

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        _LOGGER.debug("Turning off light %s", self.device_id)
        try:
            await self.coordinator.api.async_set_device_state(self.device_id, False)
            _LOGGER.debug(
                "Successfully sent turn off command for light %s", self.device_id
            )
            await self.coordinator.async_request_refresh()
        except Exception:
            _LOGGER.exception("Failed to turn off light %s", self.device_id)
            raise
