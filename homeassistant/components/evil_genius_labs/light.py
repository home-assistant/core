"""Light platform for Evil Genius Light."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from homeassistant.components import light
from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EvilGeniusEntity
from .const import DOMAIN
from .coordinator import EvilGeniusUpdateCoordinator
from .util import update_when_done

HA_NO_EFFECT = "None"
FIB_NO_EFFECT = "Solid Color"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Evil Genius light platform."""
    coordinator: EvilGeniusUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([EvilGeniusLight(coordinator)])


class EvilGeniusLight(EvilGeniusEntity, LightEntity):
    """Evil Genius Labs light."""

    _attr_name = None
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, coordinator: EvilGeniusUpdateCoordinator) -> None:
        """Initialize the Evil Genius light."""
        super().__init__(coordinator)
        self._attr_unique_id = self.coordinator.info["wiFiChipId"]
        self._attr_effect_list = [
            pattern
            for pattern in self.coordinator.data["pattern"]["options"]
            if pattern != FIB_NO_EFFECT
        ]
        self._attr_effect_list.insert(0, HA_NO_EFFECT)

    @property
    def is_on(self) -> bool:
        """Return if light is on."""
        return cast(int, self.coordinator.data["power"]["value"]) == 1

    @property
    def brightness(self) -> int:
        """Return brightness."""
        return cast(int, self.coordinator.data["brightness"]["value"])

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        """Return the rgb color value [int, int, int]."""
        return cast(
            "tuple[int, int, int]",
            tuple(
                int(val)
                for val in self.coordinator.data["solidColor"]["value"].split(",")
            ),
        )

    @property
    def effect(self) -> str:
        """Return current effect."""
        value = cast(
            str,
            self.coordinator.data["pattern"]["options"][
                self.coordinator.data["pattern"]["value"]
            ],
        )
        if value == FIB_NO_EFFECT:
            return HA_NO_EFFECT
        return value

    @update_when_done
    async def async_turn_on(
        self,
        **kwargs: Any,
    ) -> None:
        """Turn light on."""
        if (brightness := kwargs.get(light.ATTR_BRIGHTNESS)) is not None:
            async with asyncio.timeout(5):
                await self.coordinator.client.set_path_value("brightness", brightness)

        # Setting a color will change the effect to "Solid Color" so skip setting effect
        if (rgb_color := kwargs.get(light.ATTR_RGB_COLOR)) is not None:
            async with asyncio.timeout(5):
                await self.coordinator.client.set_rgb_color(*rgb_color)

        elif (effect := kwargs.get(light.ATTR_EFFECT)) is not None:
            if effect == HA_NO_EFFECT:
                effect = FIB_NO_EFFECT
            async with asyncio.timeout(5):
                await self.coordinator.client.set_path_value(
                    "pattern", self.coordinator.data["pattern"]["options"].index(effect)
                )

        async with asyncio.timeout(5):
            await self.coordinator.client.set_path_value("power", 1)

    @update_when_done
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        async with asyncio.timeout(5):
            await self.coordinator.client.set_path_value("power", 0)
