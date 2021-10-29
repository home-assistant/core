"""Light platform for Evil Genius Light."""
from __future__ import annotations

from typing import Any, cast

from async_timeout import timeout

from homeassistant.components import light

from . import EvilGeniusEntity
from .const import DOMAIN
from .util import update_when_done

HA_NO_EFFECT = "None"
FIB_NO_EFFECT = "Solid Color"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Evil Genius light platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([EvilGeniusLight(coordinator)])


class EvilGeniusLight(EvilGeniusEntity, light.LightEntity):
    """Evil Genius Labs light."""

    _attr_supported_features = (
        light.SUPPORT_BRIGHTNESS | light.SUPPORT_EFFECT | light.SUPPORT_COLOR
    )
    _attr_supported_color_modes = {light.COLOR_MODE_RGB}
    _attr_color_mode = light.COLOR_MODE_RGB

    def __init__(self, coordinator):
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
    def name(self) -> str:
        """Return name."""
        return self.coordinator.data["name"]["value"]

    @property
    def is_on(self) -> bool:
        """Return if light is on."""
        return self.coordinator.data["power"]["value"] == 1

    @property
    def brightness(self) -> int:
        """Return brightness."""
        return self.coordinator.data["brightness"]["value"]

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
        value = self.coordinator.data["pattern"]["options"][
            self.coordinator.data["pattern"]["value"]
        ]
        if value == FIB_NO_EFFECT:
            return HA_NO_EFFECT
        return value

    @update_when_done
    async def async_turn_on(
        self,
        brightness: int = None,
        effect: str = None,
        rgb_color: tuple[int, int, int] = None,
        **kwargs: Any,
    ) -> None:
        """Turn light on."""
        if brightness is not None:
            async with timeout(5):
                await self.coordinator.client.set_path_value("brightness", brightness)

        # Setting a color will change the effect to "Solid Color" so skip setting effect
        if rgb_color is not None:
            async with timeout(5):
                await self.coordinator.client.set_rgb_color(*rgb_color)
        elif effect is not None:
            if effect == HA_NO_EFFECT:
                effect = FIB_NO_EFFECT
            async with timeout(5):
                await self.coordinator.client.set_path_value(
                    "pattern", self.coordinator.data["pattern"]["options"].index(effect)
                )

        async with timeout(5):
            await self.coordinator.client.set_path_value("power", 1)

    @update_when_done
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        async with timeout(5):
            await self.coordinator.client.set_path_value("power", 0)
