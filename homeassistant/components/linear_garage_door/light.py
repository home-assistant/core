"""Linear garage door light."""

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import NiceGOConfigEntry
from .entity import LinearEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NiceGOConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nice G.O. cover."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        LinearLightEntity(coordinator, device_id, device_data.name, "light")
        for device_id, device_data in coordinator.data.items()
    )


class LinearLightEntity(LinearEntity, LightEntity):
    """Light for Linear devices."""

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_translation_key = "light"

    @property
    def is_on(self) -> bool:
        """Return if the light is on or not."""
        return self.data.light_status

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""

        await self.coordinator.api.light_on(self._device_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""

        await self.coordinator.api.light_off(self._device_id)
