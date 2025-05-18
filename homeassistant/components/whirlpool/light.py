"""Lights for the Whirlpool Appliances integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from whirlpool.oven import Cavity, Oven

from homeassistant.components.light import (
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolOvenEntity


@dataclass(frozen=True, kw_only=True)
class WhirlpoolOvenCavityLightDescription(LightEntityDescription):
    """Describes a Whirlpool oven cavity light entity."""

    value_fn: Callable[[Oven, Cavity], bool | None]


OVEN_CAVITY_LIGHTS: list[WhirlpoolOvenCavityLightDescription] = [
    WhirlpoolOvenCavityLightDescription(
        key="oven_light",
        translation_key="oven_light",
        value_fn=lambda oven, cavity: oven.get_light(cavity),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Config flow entry for Whirlpool lights."""
    entities: list = []
    appliances_manager = config_entry.runtime_data
    for oven in appliances_manager.ovens:
        cavities = []
        if oven.get_oven_cavity_exists(Cavity.Upper):
            cavities.append(Cavity.Upper)
        if oven.get_oven_cavity_exists(Cavity.Lower):
            cavities.append(Cavity.Lower)
        entities.extend(
            WhirlpoolOvenCavityLight(oven, cavity, description)
            for cavity in cavities
            for description in OVEN_CAVITY_LIGHTS
        )
    async_add_entities(entities)


class WhirlpoolOvenCavityLight(WhirlpoolOvenEntity, LightEntity):
    """Representation of an oven cavity light."""

    def __init__(
        self,
        oven: Oven,
        cavity: Cavity,
        description: WhirlpoolOvenCavityLightDescription,
    ) -> None:
        """Initialize the cavity light."""
        self.cavity = cavity
        super().__init__(oven)
        cavity_key_suffix = self.get_cavity_key_suffix(cavity)
        self.cavity = cavity
        self.entity_description: WhirlpoolOvenCavityLightDescription = description
        self._attr_unique_id = f"{oven.said}_{description.key}{cavity_key_suffix}"
        self._attr_translation_key = f"{description.key}{cavity_key_suffix}"
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return True if the cavity light is on."""
        return bool(self.oven.get_light(self.cavity))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self.oven.set_light(True, self.cavity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.oven.set_light(False, self.cavity)
